"""Race orchestration helpers — ensure_next_race, run_race_if_needed, etc.

These are the high-level orchestration functions that tie together
models, services, and the race engine.
"""

from datetime import datetime, timedelta
import json
import random

from sqlalchemy import func

from extensions import db
from models import (
    Bet, CoursePlan, Participant, Pig, Race, User, Trophy,
)
from data import (
    PIG_ORIGINS,
    MAX_INJURY_RISK, MIN_INJURY_RISK, VET_RESPONSE_MINUTES,
)
from race_engine import CourseManager

from helpers.config import get_config
from services.economy_service import (
    get_configured_bet_types,
    get_progression_settings,
    get_race_position_xp_value,
    get_race_reward_settings,
    get_recent_race_penalty_multiplier,
)
from services.finance_service import credit_user_balance
from services.pig_service import (
    apply_origin_bonus, build_unique_pig_name, generate_weight_kg_for_profile,
    get_weight_profile,
)
from services.race_service import (
    calculate_bet_odds, generate_course_segments,
    get_bet_selection_ids, get_course_theme, get_next_race_time,
    get_pig_last_race_datetime, normalize_bet_type,
    populate_race_participants,
)


def refresh_race_betting_lines(race):
    if not race or race.status != 'open':
        return
    if Bet.query.filter_by(race_id=race.id).count() > 0:
        return
    participants = Participant.query.filter_by(race_id=race.id).all()
    if not participants:
        return
    total_prob = sum(p.win_probability for p in participants) or 1.0
    participants_by_id = {participant.id: participant for participant in participants}
    for participant in participants:
        participant.win_probability = participant.win_probability / total_prob
    for participant in participants:
        participant.odds = calculate_bet_odds(participants_by_id, [participant.id], 'win')
    db.session.commit()


def get_user_active_pigs(user):
    pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
    if not pigs:
        if Pig.query.filter_by(user_id=user.id).count() > 0:
            return []
        origin = random.choice(PIG_ORIGINS)
        origin_country = origin['country']
        origin_flag = origin['flag']
        pig = Pig(
            user_id=user.id,
            name=build_unique_pig_name(f"Cochon de {user.username}", fallback_prefix='Cochon'),
            emoji='\U0001f437',
            origin_country=origin_country,
            origin_flag=origin_flag,
            lineage_name=f"Maison {user.username}",
        )
        apply_origin_bonus(pig, origin)
        pig.weight_kg = generate_weight_kg_for_profile(pig)
        db.session.add(pig)
        db.session.commit()
        return [pig]
    return pigs


def ensure_next_race():
    next_time = get_next_race_time()
    existing = Race.query.filter(
        Race.scheduled_at == next_time,
        Race.status.in_(['upcoming', 'open']),
    ).first()
    if existing:
        populate_race_participants(
            existing, respect_course_plans=True,
            allow_rebuild_if_bets=False, commit=True,
        )
        refresh_race_betting_lines(existing)
        return existing

    race = Race(scheduled_at=next_time, status='open')
    db.session.add(race)
    db.session.flush()
    # Pre-generate circuit segments so they can be previewed before the race
    segments = generate_course_segments()
    race.preview_segments_json = json.dumps(segments)
    populate_race_participants(
        race, respect_course_plans=True,
        allow_rebuild_if_bets=False, commit=True,
    )
    return race


def ensure_race_for_slot(slot_time):
    existing = Race.query.filter(
        Race.scheduled_at == slot_time,
        Race.status.in_(['upcoming', 'open']),
    ).first()
    if existing:
        populate_race_participants(
            existing, respect_course_plans=True,
            allow_rebuild_if_bets=False, commit=True,
        )
        refresh_race_betting_lines(existing)
        return existing

    race = Race(scheduled_at=slot_time, status='open')
    db.session.add(race)
    db.session.flush()
    segments = generate_course_segments()
    race.preview_segments_json = json.dumps(segments)
    populate_race_participants(
        race, respect_course_plans=True,
        allow_rebuild_if_bets=False, commit=True,
    )
    return race


def run_race_if_needed():
    now = datetime.now()
    MAX_RACES_PER_TICK = 3
    progression = get_progression_settings()
    due_races = (
        Race.query
        .filter(Race.status == 'open', Race.scheduled_at <= now)
        .order_by(Race.scheduled_at)
        .limit(MAX_RACES_PER_TICK)
        .all()
    )

    for race in due_races:
        participants = Participant.query.filter_by(race_id=race.id).all()
        if not participants:
            continue

        real_participants = [p for p in participants if p.owner_name]
        min_real = int(get_config('min_real_participants', '2'))
        mode = get_config('empty_race_mode', 'fill')
        
        has_bets = Bet.query.filter_by(race_id=race.id).count() > 0

        if len(real_participants) < min_real and mode == 'cancel' and not has_bets:
            race.status = 'cancelled'
            race.finished_at = now
            bets = Bet.query.filter_by(race_id=race.id, status='pending').all()
            for bet in bets:
                bet.status = 'refunded'
                credit_user_balance(
                    bet.user_id, bet.amount,
                    reason_code='bet_refund',
                    reason_label='Remboursement pari',
                    details=f"Course #{race.id} annulee (nombre de participants reels insuffisant).",
                    reference_type='race',
                    reference_id=race.id,
                )
            db.session.commit()
            continue

        # Mapping par pig_id (vrais cochons) ET par participant.id (PNJ)
        participants_by_id = {}
        for p in participants:
            if p.pig_id:
                participants_by_id[p.pig_id] = p
            else:
                participants_by_id[p.id] = p
        pig_start_freshness = {}
        pig_comeback_bonus_flags = {}

        pigs_for_sim = []
        for p in participants:
            if p.pig_id:
                pig = Pig.query.get(p.pig_id)
                if pig:
                    pig_start_freshness[p.pig_id] = float(pig.freshness or 100.0)
                    pig_comeback_bonus_flags[p.pig_id] = bool(pig.comeback_bonus_ready)
                    plan = CoursePlan.query.filter_by(
                        pig_id=pig.id, scheduled_at=race.scheduled_at,
                    ).first()
                    strategy_profile = (
                        plan.strategy_segments if plan
                        else {'phase_1': 35, 'phase_2': 50, 'phase_3': 80}
                    )
                    last_race_at = get_pig_last_race_datetime(pig)
                    hours_since_last_race = (
                        (race.scheduled_at - last_race_at).total_seconds() / 3600.0
                    ) if last_race_at else 999.0
                    recent_race_penalty_multiplier = get_recent_race_penalty_multiplier(
                        hours_since_last_race,
                        progression,
                    )
                    pigs_for_sim.append({
                        'id': pig.id, 'name': pig.name, 'emoji': pig.emoji,
                        'vitesse': pig.vitesse, 'endurance': pig.endurance,
                        'force': pig.force, 'agilite': pig.agilite,
                        'intelligence': pig.intelligence, 'moral': pig.moral,
                        'strategy': p.strategy,
                        'strategy_profile': strategy_profile,
                        'freshness': pig.freshness,
                        'is_happy': (pig.freshness or 0) > 90.0,
                        'speed_bonus_multiplier': progression.comeback_speed_bonus_multiplier if pig.comeback_bonus_ready else 1.0,
                        'recent_race_penalty_multiplier': recent_race_penalty_multiplier,
                    })
                else:
                    pigs_for_sim.append({
                        'id': p.id, 'name': p.name, 'emoji': p.emoji,
                        'vitesse': 20 + (1.0 / p.odds) * 100,
                        'endurance': 30, 'force': 30, 'agilite': 30,
                        'intelligence': 30, 'moral': 50, 'strategy': 50,
                        'freshness': 100.0, 'is_happy': True,
                    })
            else:
                pigs_for_sim.append({
                    'id': p.id, 'name': p.name, 'emoji': p.emoji,
                    'vitesse': 20 + (1.0 / p.odds) * 100,
                    'endurance': 30, 'force': 30, 'agilite': 30,
                    'intelligence': 30, 'moral': 50, 'strategy': 50,
                    'freshness': 100.0, 'is_happy': True,
                })

        # Reuse pre-generated segments if available, otherwise generate new ones
        if race.preview_segments_json:
            segments = json.loads(race.preview_segments_json)
        else:
            segments = generate_course_segments()
        manager = CourseManager(pigs_for_sim, segments)
        history = manager.run()
        race.replay_json = manager.to_json()

        final_pigs = sorted(
            manager.participants,
            key=lambda x: (x.finish_time or 9999, -x.distance),
        )

        order = []
        for fp in final_pigs:
            participant = participants_by_id.get(fp.id)
            if participant:
                order.append(participant)

        for i, p in enumerate(order):
            p.finish_position = i + 1

        if not order:
            race.status = 'cancelled'
            race.finished_at = now
            db.session.commit()
            continue

        winner_participant = order[0]
        race.winner_name = winner_participant.name
        race.winner_odds = winner_participant.odds
        race.finished_at = now
        race.status = 'finished'

        num_participants = len(order)

        for p in order:
            if p.pig_id:
                pig = Pig.query.get(p.pig_id)
                if not pig or not pig.is_alive:
                    continue
                owner = User.query.get(pig.user_id)
                pig.races_entered += 1
                xp_gained = get_race_position_xp_value(p.finish_position, progression)

                if owner:
                    theme = get_course_theme(race.scheduled_at)
                    reward_multiplier = theme.get('reward_multiplier', 1)
                    reward_settings = get_race_reward_settings()
                    reward = (
                        reward_settings['appearance_reward']
                        + reward_settings['position_rewards'].get(p.finish_position, 0.0)
                    ) * reward_multiplier
                    details = f"{pig.name} a termine {p.finish_position}e sur la course #{race.id}."
                    if reward_multiplier > 1:
                        details += f" Bonus {theme['name']} x{reward_multiplier} applique."
                    credit_user_balance(
                        owner.id, reward,
                        reason_code='race_reward',
                        reason_label="Prime d'éleveur",
                        details=details,
                        reference_type='race',
                        reference_id=race.id,
                    )

                if pig.challenge_mort_wager > 0:
                    wager = pig.challenge_mort_wager
                    if p.finish_position <= 3:
                        if owner:
                            credit_user_balance(
                                owner.id, wager * 3,
                                reason_code='challenge_payout',
                                reason_label='Gain Challenge de la Mort',
                                details=f"{pig.name} a survecu au Challenge de la Mort sur la course #{race.id}.",
                                reference_type='race',
                                reference_id=race.id,
                            )
                        xp_gained *= 2
                        pig.happiness = min(100, pig.happiness + 15)
                    elif p.finish_position == num_participants:
                        pig.kill(cause='challenge')
                        pig.challenge_mort_wager = 0
                        continue
                    pig.challenge_mort_wager = 0

                pig.xp += xp_gained
                if p.finish_position == 1:
                    pig.races_won += 1
                    if (pig_start_freshness.get(pig.id, 100.0) < 80.0) and owner:
                        Trophy.award(
                            user_id=owner.id,
                            code='comeback_win',
                            label='Retour Gagnant',
                            emoji='\U0001f501',
                            description="Gagner une course en partant avec moins de 80% de fraicheur.",
                            pig_name=pig.name,
                        )
                    if pig_comeback_bonus_flags.get(pig.id) and owner:
                        Trophy.award(
                            user_id=owner.id,
                            code='coup_de_collier',
                            label='Coup de Collier',
                            emoji='\U0001f4bc',
                            description="Remporter une course juste apres une periode d'inactivite.",
                            pig_name=pig.name,
                        )
                    pig.vitesse = min(
                        100,
                        pig.vitesse + (random.uniform(0.5, 1.5) * progression.race_winner_stat_gain_multiplier),
                    )
                    pig.endurance = min(
                        100,
                        pig.endurance + (random.uniform(0.5, 1.5) * progression.race_winner_stat_gain_multiplier),
                    )
                    pig.moral = min(100, pig.moral + 2)
                elif p.finish_position <= 3:
                    pig.moral = min(100, pig.moral + 1)
                    stat = random.choice(['vitesse', 'endurance', 'agilite', 'force', 'intelligence'])
                    setattr(
                        pig,
                        stat,
                        min(
                            100,
                            getattr(pig, stat) + (random.uniform(0.3, 0.8) * progression.race_podium_stat_gain_multiplier),
                        ),
                    )

                pig.energy = max(0, pig.energy - progression.race_energy_cost)
                pig.comeback_bonus_ready = False
                pig.hunger = max(0, pig.hunger - progression.race_hunger_cost)
                pig.adjust_weight(progression.race_weight_delta)
                pig.mark_bad_state_if_needed()
                pig.last_updated = datetime.utcnow()
                pig.check_level_up()

                # Rookie protection: the first races should teach the loop, not wipe the stable.
                career_races = max(0, int(pig.races_entered or 0))
                career_ramp = min(1.0, career_races / 8.0)
                rookie_protection_multiplier = 0.3 + (career_ramp * 0.7)
                base_risk_points = min(
                    MAX_INJURY_RISK,
                    max(MIN_INJURY_RISK, float(pig.injury_risk or MIN_INJURY_RISK)),
                )
                base_risk = (base_risk_points / 100.0) * rookie_protection_multiplier
                fatigue_factor = 1.0 + max(0, (50 - pig.energy) / 100)
                hunger_factor = 1.0 + max(0, (30 - pig.hunger) / 100)
                weight_profile = get_weight_profile(pig)
                effective_risk = min(
                    0.25,
                    base_risk * fatigue_factor * hunger_factor * weight_profile['injury_factor'],
                )
                if random.random() < effective_risk and not pig.is_injured:
                    pig.is_injured = True
                    pig.vet_deadline = datetime.utcnow() + timedelta(minutes=VET_RESPONSE_MINUTES)
                    pig.challenge_mort_wager = 0
                else:
                    pig.injury_risk = min(
                        MAX_INJURY_RISK,
                        max(MIN_INJURY_RISK, float(pig.injury_risk or MIN_INJURY_RISK)) + random.uniform(0.1, 0.3),
                    )

                if pig.max_races and pig.races_entered >= pig.max_races:
                    pig.retire()

        bets = Bet.query.filter_by(race_id=race.id, status='pending').all()
        finish_order_ids = [participant.id for participant in order]
        bet_types = get_configured_bet_types()
        for bet in bets:
            bet_type = normalize_bet_type(getattr(bet, 'bet_type', None))
            bet_config = bet_types.get(bet_type, bet_types['win'])
            expected_count = bet_config['selection_count']
            top_n = bet_config.get('top_n', expected_count)
            order_matters = bet_config.get('order_matters', True)

            selection_ids = get_bet_selection_ids(bet, participants_by_id)

            if len(selection_ids) == expected_count:
                top_finishers = finish_order_ids[:top_n]
                is_winner = False

                if order_matters:
                    if top_finishers[:expected_count] == selection_ids:
                        is_winner = True
                else:
                    if all(sid in top_finishers for sid in selection_ids):
                        is_winner = True

                if is_winner:
                    winnings = round(bet.amount * bet.odds_at_bet, 2)
                    bet.status = 'won'
                    bet.winnings = winnings
                    credit_user_balance(
                        bet.user_id, winnings,
                        reason_code='bet_payout',
                        reason_label='Gain de pari',
                        details=f"Ticket {bet_config['label'].lower()} gagnant sur la course #{race.id}: {bet.pig_name}.",
                        reference_type='bet',
                        reference_id=bet.id,
                    )
                else:
                    bet.status = 'lost'
                    bet.winnings = 0.0
            else:
                bet.status = 'lost'
                bet.winnings = 0.0

        db.session.commit()

    if due_races:
        ensure_next_race()


def get_race_history_entries():
    races = (
        Race.query
        .filter(Race.status.in_(['finished', 'cancelled']))
        .order_by(Race.finished_at.desc(), Race.id.desc())
        .all()
    )
    if not races:
        return []

    race_ids = [race.id for race in races]
    participants = Participant.query.filter(Participant.race_id.in_(race_ids)).all()
    participants_by_race = {}
    for participant in participants:
        participants_by_race.setdefault(participant.race_id, []).append(participant)

    bet_stats_rows = (
        db.session.query(
            Bet.race_id,
            func.count(Bet.id),
            func.coalesce(func.sum(Bet.amount), 0.0),
            func.coalesce(func.sum(Bet.winnings), 0.0),
        )
        .filter(Bet.race_id.in_(race_ids))
        .group_by(Bet.race_id)
        .all()
    )
    bet_stats_by_race = {
        race_id: {
            'bet_count': bet_count,
            'total_staked': round(float(total_staked or 0.0), 2),
            'total_paid_out': round(float(total_paid_out or 0.0), 2),
        }
        for race_id, bet_count, total_staked, total_paid_out in bet_stats_rows
    }

    entries = []
    for race in races:
        ordered_participants = sorted(
            participants_by_race.get(race.id, []),
            key=lambda participant: (
                participant.finish_position is None,
                participant.finish_position or 999,
                participant.id,
            ),
        )
        stats = bet_stats_by_race.get(
            race.id, {'bet_count': 0, 'total_staked': 0.0, 'total_paid_out': 0.0},
        )
        entries.append({
            'race': race,
            'participants': ordered_participants,
            'podium': ordered_participants[:3],
            'winner': ordered_participants[0] if ordered_participants else None,
            'player_count': sum(1 for p in ordered_participants if p.owner_name),
            'npc_count': sum(1 for p in ordered_participants if not p.owner_name),
            'bet_count': stats['bet_count'],
            'total_staked': stats['total_staked'],
            'total_paid_out': stats['total_paid_out'],
        })
    return entries
