from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import random

from extensions import db
from models import User, Pig
from data import (
    SCHOOL_COOLDOWN_MINUTES,
    PIG_EMOJIS, PIG_ORIGINS, STAT_LABELS, STAT_DESCRIPTIONS, RARITIES, BREEDING_COST,
    OFFICE_SNACKS, SNACK_SHARE_DAILY_LIMIT, PIG_TYPING_WORDS,
)
from helpers import (
    get_user_active_pigs,
    get_cooldown_remaining, format_duration_short, get_seconds_until,
    get_cereals_dict, get_trainings_dict, get_school_lessons_dict,
)
from utils.time_utils import is_weekend_truce_active

from services.finance_service import (
    maybe_grant_emergency_relief, reserve_pig_challenge_slot, release_pig_challenge_slot,
)
from services.pig_service import (
    calculate_pig_power, xp_for_level, get_weight_profile, get_adoption_cost,
    get_active_listing_count, get_pig_slot_count, get_max_pig_slots,
    get_feeding_cost_multiplier, get_lineage_label, get_pig_heritage_value,
    can_retire_into_heritage, retire_pig_into_heritage, create_offspring,
    apply_origin_bonus, generate_weight_kg_for_profile, get_freshness_bonus,
    get_pig_performance_flags, reset_snack_share_limit_if_needed,
    is_pig_name_taken, build_unique_pig_name,
)

pig_bp = Blueprint('pig', __name__)


@pig_bp.route('/mon-cochon')
def mon_cochon():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    relief_amount = maybe_grant_emergency_relief(user)
    if relief_amount > 0:
        db.session.refresh(user)
        flash(f"🛟 Prime d'élevage d'urgence: +{relief_amount:.0f} 🪙 pour relancer ton élevage.", "success")
    reset_snack_share_limit_if_needed(user)
    db.session.commit()
    pigs = get_user_active_pigs(user)
    adoption_cost = get_adoption_cost(user)
    active_listing_count = get_active_listing_count(user)
    feeding_multiplier = get_feeding_cost_multiplier(user)
    max_slots = get_max_pig_slots(user)

    pigs_data = []
    for p in pigs:
        p.update_vitals()
        races_remaining = max(0, (p.max_races or 80) - p.races_entered)
        age_days = (datetime.utcnow() - p.created_at).days if p.created_at else 0
        rarity_info = RARITIES.get(p.rarity or 'commun', RARITIES['commun'])
        school_cooldown = get_cooldown_remaining(p.last_school_at, SCHOOL_COOLDOWN_MINUTES)
        vet_seconds_left = get_seconds_until(p.vet_deadline) if p.is_injured else 0
        weight_profile = get_weight_profile(p)
        freshness_bonus = get_freshness_bonus(p)
        pigs_data.append({
            'pig': p,
            'lineage_label': get_lineage_label(p),
            'heritage_value': get_pig_heritage_value(p),
            'can_retire_into_heritage': can_retire_into_heritage(p),
            'races_remaining': races_remaining,
            'age_days': age_days,
            'rarity_info': rarity_info,
            'power': round(calculate_pig_power(p), 1),
            'xp_next': xp_for_level(p.level + 1),
            'school_cooldown': school_cooldown,
            'school_cooldown_label': format_duration_short(school_cooldown),
            'vet_seconds_left': vet_seconds_left,
            'vet_deadline_label': format_duration_short(vet_seconds_left),
            'weight_profile': weight_profile,
            'freshness_bonus': freshness_bonus,
            'performance_flags': get_pig_performance_flags(p),
            'weekend_truce_active': is_weekend_truce_active(),
            'share_snacks_remaining': max(0, SNACK_SHARE_DAILY_LIMIT - (user.snack_shares_today or 0)),
        })

    return render_template('mon_cochon.html',
        user=user, pigs_data=pigs_data, cereals=get_cereals_dict(), trainings=get_trainings_dict(),
        school_lessons=get_school_lessons_dict(), school_cooldown_minutes=SCHOOL_COOLDOWN_MINUTES,
        pig_emojis=PIG_EMOJIS, stat_labels=STAT_LABELS, stat_descriptions=STAT_DESCRIPTIONS,
        adoption_cost=adoption_cost, active_listing_count=active_listing_count,
        feeding_multiplier=feeding_multiplier, max_slots=max_slots, breeding_cost=BREEDING_COST
    )


@pig_bp.route('/adopt-second-pig')
def adopt_second_pig():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    active_pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
    max_slots = get_max_pig_slots(user)
    if get_pig_slot_count(user) >= max_slots:
        flash(f"Tu as déjà le maximum de cochons ({max_slots}) !", "warning")
        return redirect(url_for('pig.mon_cochon'))

    cost = get_adoption_cost(user)
    if cost is None:
        flash("Impossible d'adopter un nouveau cochon pour l'instant.", "warning")
        return redirect(url_for('pig.mon_cochon'))
    if not user.pay(
        cost,
        reason_code='pig_adoption',
        reason_label='Adoption de cochon',
        details="Ouverture d'une nouvelle place dans l'elevage.",
        reference_type='user',
        reference_id=user.id,
    ):
        flash(f"Il te faut {cost:.0f} 🪙 pour adopter un nouveau cochon !", "error")
        return redirect(url_for('pig.mon_cochon'))

    origin = random.choice(PIG_ORIGINS)
    new_pig = Pig(
        user_id=user.id,
        name=build_unique_pig_name(f"Recrue de {user.username}" if active_pigs else f"Rescapé de {user.username}", fallback_prefix='Recrue'),
        emoji='🐖',
        origin_country=origin['country'],
        origin_flag=origin['flag'],
        lineage_name=f"Maison {user.username}",
    )
    apply_origin_bonus(new_pig, origin)
    new_pig.weight_kg = generate_weight_kg_for_profile(new_pig)
    db.session.add(new_pig)
    db.session.commit()
    if active_pigs:
        flash("✨ Nouveau cochon adopté ! Bienvenue dans la porcherie, mais attention: chaque bouche en plus rend l'alimentation plus coûteuse.", "success")
    else:
        flash("✨ Un cochon de secours rejoint ton élevage. C'est reparti.", "success")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/feed', methods=['POST'])
def feed():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))

    pig.update_vitals()
    cereals = get_cereals_dict()
    cereal_key = request.form.get('cereal')
    if cereal_key not in cereals:
        return redirect(url_for('pig.mon_cochon'))
    cereal = cereals[cereal_key]
    if pig.hunger >= 95:
        flash("Ton cochon n'a plus faim !", "warning")
        return redirect(url_for('pig.mon_cochon'))
    feeding_multiplier = get_feeding_cost_multiplier(user)
    effective_cost = round(cereal['cost'] * feeding_multiplier, 2)
    if not user.pay(
        effective_cost,
        reason_code='feed_purchase',
        reason_label='Nourriture achetee',
        details=f"{cereal['name']} pour {pig.name}. Cout x{feeding_multiplier:.2f} avec {user.pig_count} cochon(s).",
        reference_type='pig',
        reference_id=pig.id,
    ):
        flash("Pas assez de BitGroins !", "error")
        return redirect(url_for('pig.mon_cochon'))

    pig.feed(cereal)
    db.session.commit()
    flash(f"{cereal['emoji']} {cereal['name']} donné ! Miam ! Coût réel: {effective_cost:.0f} 🪙 (x{feeding_multiplier:.2f} de pression d'élevage).", "success")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/share-snack', methods=['POST'])
def share_snack():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    reset_snack_share_limit_if_needed(user)

    recipient_pig = Pig.query.get(request.form.get('pig_id', type=int))
    if not recipient_pig or not recipient_pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))
    if recipient_pig.user_id == user.id:
        flash("Tu ne peux pas lancer un encas sur ton propre cochon via cette action.", "warning")
        return redirect(url_for('pig.mon_cochon'))

    snack_key = request.form.get('snack')
    snack = OFFICE_SNACKS.get(snack_key)
    if not snack:
        flash("En-cas de bureau inconnu.", "error")
        return redirect(url_for('pig.mon_cochon'))

    if (user.snack_shares_today or 0) >= SNACK_SHARE_DAILY_LIMIT:
        flash(f"Tu as deja distribue tes {SNACK_SHARE_DAILY_LIMIT} en-cas solidaires aujourd'hui.", "warning")
        return redirect(url_for('pig.mon_cochon'))

    recipient_pig.update_vitals()
    recipient_pig.hunger = min(100, recipient_pig.hunger + snack['hunger_restore'])
    recipient_pig.last_fed_at = datetime.utcnow()
    recipient_pig.last_updated = recipient_pig.last_fed_at
    recipient_pig.reset_freshness()
    user.snack_shares_today = (user.snack_shares_today or 0) + 1
    user.snack_share_reset_at = datetime.utcnow()
    db.session.commit()

    recipient_name = recipient_pig.owner.username if recipient_pig.owner else 'ton collegue'
    flash(f"Tu as lance un trognon de pomme au cochon de {recipient_name}, quel geste noble !", "success")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/train', methods=['POST'])
def train():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))

    pig.update_vitals()
    if not pig.can_train:
        flash("Ton cochon est blessé. Passe d'abord par le vétérinaire.", "warning")
        return redirect(url_for('api.veterinaire', pig_id=pig.id))
    trainings = get_trainings_dict()
    training_key = request.form.get('training')
    if training_key not in trainings:
        return redirect(url_for('pig.mon_cochon'))
    training = trainings[training_key]
    if training['energy_cost'] > 0 and pig.energy < training['energy_cost']:
        flash("Ton cochon est trop fatigué !", "error")
        return redirect(url_for('pig.mon_cochon'))
    if pig.hunger < training.get('hunger_cost', 0):
        flash("Ton cochon a trop faim pour s'entraîner !", "error")
        return redirect(url_for('pig.mon_cochon'))
    if pig.happiness < training.get('min_happiness', 0):
        flash("Ton cochon n'est pas assez heureux !", "error")
        return redirect(url_for('pig.mon_cochon'))
    pig.train(training)
    db.session.commit()
    flash(f"{training['emoji']} {training['name']} terminé !", "success")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/school', methods=['POST'])
def school():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))

    pig.update_vitals()
    if not pig.can_school:
        flash("L'école attendra. Ton cochon doit d'abord passer au vétérinaire.", "warning")
        return redirect(url_for('api.veterinaire', pig_id=pig.id))
    school_lessons = get_school_lessons_dict()
    lesson_key = request.form.get('lesson')
    if lesson_key not in school_lessons:
        flash("Cours introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))

    lesson = school_lessons[lesson_key]
    cooldown = get_cooldown_remaining(pig.last_school_at, SCHOOL_COOLDOWN_MINUTES)
    if cooldown > 0:
        flash(f"La salle de classe est fermee pour l'instant. Reviens dans {format_duration_short(cooldown)}.", "warning")
        return redirect(url_for('pig.mon_cochon'))

    answer_idx = request.form.get('answer_idx', type=int)
    answers = lesson['answers']
    if answer_idx is None or answer_idx < 0 or answer_idx >= len(answers):
        flash("Reponse invalide !", "error")
        return redirect(url_for('pig.mon_cochon'))

    if pig.energy < lesson['energy_cost']:
        flash("Ton cochon est trop fatigue pour suivre ce cours.", "error")
        return redirect(url_for('pig.mon_cochon'))
    if pig.hunger < lesson['hunger_cost']:
        flash("Ton cochon a trop faim pour se concentrer.", "error")
        return redirect(url_for('pig.mon_cochon'))
    if pig.happiness < lesson['min_happiness']:
        flash("Ton cochon boude l'ecole aujourd'hui. Remonte-lui le moral d'abord.", "warning")
        return redirect(url_for('pig.mon_cochon'))

    selected_answer = answers[answer_idx]
    category = pig.study(lesson, correct=selected_answer['correct'])
    if category == 'success':
        feedback_prefix = "Cours valide avec mention groin-tres-bien."
    else:
        feedback_prefix = "Le cours etait plus complique que prevu."

    db.session.commit()
    flash(f"{lesson['emoji']} {lesson['name']} - {feedback_prefix} {selected_answer['feedback']}", category)
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/rename-pig', methods=['POST'])
def rename_pig():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))
    new_name = request.form.get('name', '').strip()
    new_emoji = request.form.get('emoji', '').strip()
    if new_name:
        if not 2 <= len(new_name) <= 30:
            flash("Le nom du cochon doit contenir entre 2 et 30 caractères.", "warning")
            return redirect(url_for('pig.mon_cochon'))
        if is_pig_name_taken(new_name, exclude_pig_id=pig.id):
            flash("Ce nom de cochon existe déjà. Choisis un nom unique !", "error")
            return redirect(url_for('pig.mon_cochon'))
        pig.name = new_name
    if new_emoji and new_emoji in PIG_EMOJIS:
        pig.emoji = new_emoji
    db.session.commit()
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/challenge-mort', methods=['POST'])
def challenge_mort():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))

    pig.update_vitals()
    if pig.is_injured:
        flash("Impossible d'inscrire un cochon blessé au Challenge de la Mort.", "error")
        return redirect(url_for('api.veterinaire', pig_id=pig.id))
    wager = request.form.get('wager', type=float)
    if not wager or wager < 10:
        flash("Mise minimum : 10 🪙 pour le Challenge de la Mort !", "error")
        return redirect(url_for('pig.mon_cochon'))
    if pig.challenge_mort_wager > 0:
        flash("Tu es déjà inscrit au Challenge de la Mort !", "warning")
        return redirect(url_for('pig.mon_cochon'))
    if pig.energy <= 20 or pig.hunger <= 20:
        flash("Ton cochon est trop faible pour le Challenge !", "error")
        return redirect(url_for('pig.mon_cochon'))

    if not user.pay(
        wager,
        reason_code='challenge_entry',
        reason_label='Inscription Challenge de la Mort',
        details=f"{pig.name} engagé pour {wager:.0f} 🪙.",
        reference_type='pig',
        reference_id=pig.id,
    ):
        flash("T'as pas les moyens de jouer avec la vie de ton cochon !", "error")
        return redirect(url_for('pig.mon_cochon'))
    if not reserve_pig_challenge_slot(pig.id, wager):
        db.session.rollback()
        flash("Tu es déjà inscrit au Challenge de la Mort !", "warning")
        return redirect(url_for('pig.mon_cochon'))

    db.session.commit()
    flash(f"💀 {pig.name} inscrit au Challenge de la Mort ({wager:.0f} 🪙) ! Bonne chance...", "success")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/cancel-challenge', methods=['POST'])
def cancel_challenge():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))

    if pig.challenge_mort_wager <= 0:
        return redirect(url_for('pig.mon_cochon'))

    refund = release_pig_challenge_slot(pig.id)
    if refund <= 0:
        flash("Le challenge a déjà été annulé ou réglé ailleurs.", "warning")
        return redirect(url_for('pig.mon_cochon'))
    user.earn(
        refund,
        reason_code='challenge_refund',
        reason_label='Remboursement Challenge de la Mort',
        details=f"Annulation du challenge pour {pig.name}.",
        reference_type='pig',
        reference_id=pig.id,
    )
    flash(f"😰 Challenge annulé pour {pig.name}... Remboursement : {refund:.0f} 🪙 (50%)", "warning")
    return redirect(url_for('pig.mon_cochon'))

@pig_bp.route('/breed-pig', methods=['POST'])
def breed_pig():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    parent_a = Pig.query.get(request.form.get('pig_id', type=int))
    parent_b = Pig.query.get(request.form.get('partner_id', type=int))
    child_name = request.form.get('child_name', '').strip()

    if not parent_a or not parent_b or parent_a.user_id != user.id or parent_b.user_id != user.id:
        flash("Parents introuvables !", "error")
        return redirect(url_for('pig.mon_cochon'))
    if parent_a.id == parent_b.id:
        flash("Il faut deux cochons distincts pour lancer une lignée.", "warning")
        return redirect(url_for('pig.mon_cochon'))
    if not parent_a.is_alive or not parent_b.is_alive:
        flash("La reproduction exige deux cochons actifs.", "warning")
        return redirect(url_for('pig.mon_cochon'))
    if get_pig_slot_count(user) >= get_max_pig_slots(user):
        flash("La porcherie est pleine. Vends, retire ou perds un cochon avant de lancer une nouvelle portée.", "warning")
        return redirect(url_for('pig.mon_cochon'))
    if not user.pay(
        BREEDING_COST,
        reason_code='pig_breeding',
        reason_label='Lancement de portee',
        details=f"Portee entre {parent_a.name} et {parent_b.name}.",
        reference_type='user',
        reference_id=user.id,
    ):
        flash(f"Il faut {BREEDING_COST:.0f} 🪙 pour financer la portée.", "error")
        return redirect(url_for('pig.mon_cochon'))

    if child_name and is_pig_name_taken(child_name):
        flash("Ce nom de cochon existe déjà. Choisis un nom unique pour la portée.", "error")
        return redirect(url_for('pig.mon_cochon'))

    piglet = create_offspring(user, parent_a, parent_b, name=child_name or None)
    db.session.add(piglet)
    db.session.commit()
    flash(f"🐣 Nouvelle portée ! {piglet.name} rejoint la lignée {piglet.lineage_name} (génération {piglet.generation}). Pense à son budget nourriture: plus tu as de cochons, plus chaque repas coûte cher.", "success")
    return redirect(url_for('pig.mon_cochon'))

@pig_bp.route('/retire-pig-heritage', methods=['POST'])
def retire_pig_heritage():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    pig = Pig.query.get(request.form.get('pig_id', type=int))
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))
    bonus = retire_pig_into_heritage(user, pig)
    if bonus <= 0:
        flash("Seuls les cochons légendaires ou les champions à 3 victoires peuvent être retirés comme ancêtres fondateurs.", "warning")
        return redirect(url_for('pig.mon_cochon'))
    flash(f"🏛️ {pig.name} prend une retraite d'honneur. La porcherie gagne +{bonus:.1f} d'héritage permanent et sa lignée est renforcée.", "success")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/sacrifice-pig', methods=['POST'])
def sacrifice_pig():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))

    pig.kill(cause='sacrifice_volontaire')
    db.session.commit()
    flash(f"🔪 {pig.name} a été envoyé à l'abattoir volontairement. Paix à ses côtelettes.", "warning")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/typing-challenge/<int:pig_id>')
def typing_challenge(pig_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    pig = Pig.query.get(pig_id)

    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))
    
    if pig.is_injured:
        flash("Ton cochon est blesse. Rends-toi chez le veterinaire.", "warning")
        return redirect(url_for('pig.mon_cochon'))
    
    cooldown = get_cooldown_remaining(pig.last_school_at, SCHOOL_COOLDOWN_MINUTES)
    if cooldown > 0:
        flash(f"La salle de dactylo est fermee. Reviens dans {format_duration_short(cooldown)}.", "warning")
        return redirect(url_for('pig.mon_cochon'))
    
    words = random.sample(PIG_TYPING_WORDS, 15)
    return render_template('typing_game.html', pig=pig, words=words)


@pig_bp.route('/typing-complete', methods=['POST'])
def typing_complete():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    pig_id = request.form.get('pig_id', type=int)
    time_taken = request.form.get('time_taken', type=float)
    errors = request.form.get('errors', type=int)
    
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != session['user_id'] or not pig.is_alive:
        return redirect(url_for('pig.mon_cochon'))

    # Cooldown check again for safety
    cooldown = get_cooldown_remaining(pig.last_school_at, SCHOOL_COOLDOWN_MINUTES)
    if cooldown > 0:
        return redirect(url_for('pig.mon_cochon'))

    # Calculate performance
    # Example: 15 words, ideal time around 20-30s.
    # Score could be based on WPM
    wpm = (15 / time_taken) * 60 if time_taken > 0 else 0
    
    if wpm > 40 and errors <= 2:
        pig.vitesse = min(100, pig.vitesse + 1.5)
        pig.agilite = min(100, pig.agilite + 1.0)
        bonus_msg = "Excellent ! +1.5 Vitesse, +1.0 Agilite."
        category = "success"
    elif wpm > 20:
        pig.vitesse = min(100, pig.vitesse + 0.5)
        bonus_msg = "Pas mal. +0.5 Vitesse."
        category = "success"
    else:
        bonus_msg = "Tu peux faire mieux !"
        category = "warning"

    pig.xp += 20
    pig.last_school_at = datetime.utcnow()
    pig.last_updated = pig.last_school_at
    pig.reset_freshness()
    pig.mark_bad_state_if_needed()
    pig.check_level_up()
    db.session.commit()
    
    flash(f"🏆 Typing Derby termine ! {bonus_msg} (WPM: {wpm:.1f}, Erreurs: {errors})", category)
    return redirect(url_for('pig.mon_cochon'))
