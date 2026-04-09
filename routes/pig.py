from flask import Blueprint, jsonify, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import random

from config.gameplay_defaults import OFFICE_SNACKS
from content.flavor_texts import PIG_TYPING_WORDS
from content.pigs_catalog import PIG_EMOJIS, PIG_ORIGINS, RARITIES
from content.stats_metadata import STAT_DESCRIPTIONS, STAT_LABELS
from exceptions import BusinessRuleError, InsufficientFundsError
from extensions import db, limiter
from helpers.game_data import get_cereals_dict, get_school_lessons_dict, get_trainings_dict
from helpers.race import get_user_active_pigs
from helpers.time_helpers import format_duration_short, get_cooldown_remaining, get_seconds_until
from models import User, Pig, PigAvatar
from services.economy_service import get_breeding_cost_value, get_progression_settings
from utils.time_utils import is_weekend_truce_active

from services.finance_service import (
    credit_user, debit_user, maybe_grant_emergency_relief, release_pig_challenge_slot,
)
from services.gameplay_settings_service import get_gameplay_settings
from services.pig_lineage_service import (
    apply_origin_bonus,
    build_pig_lineage_tree,
    build_unique_pig_name,
    create_offspring,
    get_lineage_label, get_pig_heritage_value,
    is_pig_name_taken,
    random_pig_sex,
)
from services.pig_power_service import (
    calculate_pig_power,
    check_level_up,
    generate_weight_kg_for_profile,
    get_freshness_bonus,
    get_pig_performance_flags,
    get_weight_profile,
    xp_for_level,
)
from services.pig_service import (
    can_retire_into_heritage, retire_pig_into_heritage, get_adoption_cost,
    get_active_listing_count, get_pig_slot_count, get_max_pig_slots,
    reset_snack_share_limit_if_needed,
    enter_pig_death_challenge, feed_pig_for_user, kill_pig,
    get_learning_decay_multiplier, get_user_cereal_inventory_dict, register_learning_session,
    study_pig_for_user, train_pig_for_user, update_pig_vitals,
)

pig_bp = Blueprint('pig', __name__)


def _can_view_lineage(user, pig):
    return bool(
        user
        and pig
        and (
            user.is_admin
            or pig.user_id == user.id
            or pig.haras_listed
            or not pig.is_alive
        )
    )


@pig_bp.route('/api/pigs/<int:pig_id>/lineage-tree')
def pig_lineage_tree(pig_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401

    user = db.session.get(User, session['user_id'])
    pig = db.session.get(Pig, pig_id)
    if not user or not pig:
        return jsonify({'error': 'Cochon introuvable'}), 404
    if not _can_view_lineage(user, pig):
        return jsonify({'error': 'Accès interdit'}), 403

    max_depth = max(1, min(6, request.args.get('depth', 4, type=int)))
    payload = build_pig_lineage_tree(pig.id, max_depth=max_depth)
    if payload is None:
        return jsonify({'error': 'Arbre généalogique introuvable'}), 404
    return jsonify(payload)


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
    max_slots = get_max_pig_slots(user)
    breeding_cost = get_breeding_cost_value()
    user_inventory = get_user_cereal_inventory_dict(user.id)
    gameplay = get_gameplay_settings()

    pigs_data = []
    for p in pigs:
        update_pig_vitals(p)
        races_remaining = p.races_remaining
        age_days = (datetime.utcnow() - p.created_at).days if p.created_at else 0
        rarity_info = RARITIES.get(p.rarity or 'commun', RARITIES['commun'])
        school_cooldown = get_cooldown_remaining(p.last_school_at, gameplay.school_cooldown_minutes)
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
            'share_snacks_remaining': max(0, gameplay.snack_share_daily_limit - (user.snack_shares_today or 0)),
        })

    available_avatars = PigAvatar.query.order_by(PigAvatar.name).all()
    return render_template('mon_cochon.html',
        user=user, pigs_data=pigs_data, cereals=get_cereals_dict(), trainings=get_trainings_dict(),
        school_lessons=get_school_lessons_dict(), school_cooldown_minutes=gameplay.school_cooldown_minutes,
        pig_emojis=PIG_EMOJIS, stat_labels=STAT_LABELS, stat_descriptions=STAT_DESCRIPTIONS,
        adoption_cost=adoption_cost, active_listing_count=active_listing_count,
        user_inventory=user_inventory, max_slots=max_slots, breeding_cost=breeding_cost,
        available_avatars=available_avatars,
    )


@pig_bp.route('/adopt-second-pig')
def adopt_second_pig():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    active_pigs = get_user_active_pigs(user)
    max_slots = get_max_pig_slots(user)
    if get_pig_slot_count(user) >= max_slots:
        flash(f"Tu as déjà le maximum de cochons ({max_slots}) !", "warning")
        return redirect(url_for('pig.mon_cochon'))

    cost = get_adoption_cost(user)
    if cost is None:
        flash("Impossible d'adopter un nouveau cochon pour l'instant.", "warning")
        return redirect(url_for('pig.mon_cochon'))
    try:
        debit_user(
            user,
            cost,
            reason_code='pig_adoption',
            reason_label='Adoption de cochon',
            details="Ouverture d'une nouvelle place dans l'elevage.",
            reference_type='user',
            reference_id=user.id,
            commit=False,
        )
    except InsufficientFundsError:
        flash(f"Il te faut {cost:.0f} 🪙 pour adopter un nouveau cochon !", "error")
        return redirect(url_for('pig.mon_cochon'))

    origin = random.choice(PIG_ORIGINS)
    new_pig = Pig(
        user_id=user.id,
        name=build_unique_pig_name(f"Recrue de {user.username}" if active_pigs else f"Rescapé de {user.username}", fallback_prefix='Recrue'),
        emoji='🐖',
        sex=random_pig_sex(),
        origin_country=origin['country'],
        origin_flag=origin['flag'],
        lineage_name=f"Maison {user.username}",
        max_races=get_pig_settings().default_max_races,
    )
    apply_origin_bonus(new_pig, origin)
    from services.pig_lineage_service import init_pig_genes_random
    init_pig_genes_random(new_pig)
    new_pig.weight_kg = generate_weight_kg_for_profile(new_pig)
    db.session.add(new_pig)
    db.session.commit()
    if active_pigs:
        flash("✨ Nouveau cochon adopté ! Bienvenue dans la porcherie, mais attention: chaque bouche en plus rend l'alimentation plus coûteuse.", "success")
    else:
        flash("✨ Un cochon de secours rejoint ton élevage. C'est reparti.", "success")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/feed', methods=['POST'])
@limiter.limit("15 per minute")
def feed():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        result = feed_pig_for_user(
            session['user_id'],
            request.form.get('pig_id', type=int),
            request.form.get('cereal'),
        )
        flash(result['message'], result.get('category', 'success'))
    except BusinessRuleError as exc:
        flash(str(exc), "error")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/share-snack', methods=['POST'])
@limiter.limit("10 per minute")
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

    gameplay = get_gameplay_settings()
    if (user.snack_shares_today or 0) >= gameplay.snack_share_daily_limit:
        flash(f"Tu as deja distribue tes {gameplay.snack_share_daily_limit} en-cas solidaires aujourd'hui.", "warning")
        return redirect(url_for('pig.mon_cochon'))

    update_pig_vitals(recipient_pig)
    recipient_pig.hunger = min(100, recipient_pig.hunger + snack['hunger_restore'])
    recipient_pig.last_fed_at = datetime.utcnow()
    recipient_pig.register_positive_interaction(recipient_pig.last_fed_at)
    user.snack_shares_today = (user.snack_shares_today or 0) + 1
    user.snack_share_reset_at = datetime.utcnow()
    db.session.commit()

    recipient_name = recipient_pig.owner.username if recipient_pig.owner else 'ton collegue'
    flash(f"Tu as lance un trognon de pomme au cochon de {recipient_name}, quel geste noble !", "success")
    redirect_to = request.form.get('redirect_to', '').strip()
    if redirect_to:
        return redirect(url_for('auth.profil_public', username=redirect_to))
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/train', methods=['POST'])
@limiter.limit("15 per minute")
def train():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        result = train_pig_for_user(
            session['user_id'],
            request.form.get('pig_id', type=int),
            request.form.get('training'),
        )
        flash(result['message'], result.get('category', 'success'))
    except BusinessRuleError as exc:
        flash(str(exc), "error")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/school', methods=['POST'])
@limiter.limit("10 per minute")
def school():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        result = study_pig_for_user(
            session['user_id'],
            request.form.get('pig_id', type=int),
            request.form.get('lesson'),
            request.form.get('answer_idx', type=int),
            cooldown_minutes=get_gameplay_settings().school_cooldown_minutes,
        )
        flash(result['message'], result.get('category', 'success'))
    except BusinessRuleError as exc:
        flash(str(exc), "error")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/rename-pig', methods=['POST'])
@limiter.limit("5 per minute")
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


@pig_bp.route('/choose-avatar', methods=['POST'])
@limiter.limit("10 per minute")
def choose_avatar():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))
    avatar_id = request.form.get('avatar_id', type=int)
    if avatar_id:
        avatar = PigAvatar.query.get(avatar_id)
        if avatar:
            pig.avatar_id = avatar.id
    else:
        pig.avatar_id = None
    db.session.commit()
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/challenge-mort', methods=['POST'])
@limiter.limit("5 per minute")
def challenge_mort():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        result = enter_pig_death_challenge(
            session['user_id'],
            request.form.get('pig_id', type=int),
            request.form.get('wager', type=float),
        )
        flash(result['message'], result.get('category', 'success'))
    except BusinessRuleError as exc:
        flash(str(exc), "error")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/cancel-challenge', methods=['POST'])
@limiter.limit("5 per minute")
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
    credit_user(
        user,
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
@limiter.limit("5 per minute")
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
    if parent_a.sex == parent_b.sex:
        flash("La reproduction nécessite un mâle et une femelle !", "warning")
        return redirect(url_for('pig.mon_cochon'))
    if get_pig_slot_count(user) >= get_max_pig_slots(user):
        flash("La porcherie est pleine. Vends, retire ou perds un cochon avant de lancer une nouvelle portée.", "warning")
        return redirect(url_for('pig.mon_cochon'))
    breeding_cost = get_breeding_cost_value()
    try:
        debit_user(
            user,
            breeding_cost,
            reason_code='pig_breeding',
            reason_label='Lancement de portee',
            details=f"Portee entre {parent_a.name} et {parent_b.name}.",
            reference_type='user',
            reference_id=user.id,
            commit=False,
        )
    except InsufficientFundsError:
        flash(f"Il faut {breeding_cost:.0f} 🪙 pour financer la portée.", "error")
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
@limiter.limit("5 per minute")
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
@limiter.limit("5 per minute")
def sacrifice_pig():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('pig.mon_cochon'))

    kill_pig(pig, cause='sacrifice_volontaire')
    flash(f"🔪 {pig.name} a été envoyé à l'abattoir volontairement. Paix à ses côtelettes.", "warning")
    return redirect(url_for('pig.mon_cochon'))


@pig_bp.route('/typing-challenge/<int:pig_id>')
@pig_bp.route('/typing-challenge/<int:pig_id>/')
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
    
    cooldown = get_cooldown_remaining(pig.last_school_at, get_gameplay_settings().school_cooldown_minutes)
    if cooldown > 0:
        flash(f"La salle de dactylo est fermee. Reviens dans {format_duration_short(cooldown)}.", "warning")
        return redirect(url_for('pig.mon_cochon'))
    
    words = random.sample(PIG_TYPING_WORDS, 15)
    return render_template('typing_game.html', pig=pig, words=words)


@pig_bp.route('/typing-complete', methods=['GET', 'POST'])
@pig_bp.route('/typing-complete/', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def typing_complete():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    if request.method != 'POST':
        return redirect(url_for('pig.mon_cochon'))
    
    pig_id = request.form.get('pig_id', type=int)
    time_taken = request.form.get('time_taken', type=float)
    errors = request.form.get('errors', type=int)
    
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != session['user_id'] or not pig.is_alive:
        return redirect(url_for('pig.mon_cochon'))

    # Cooldown check again for safety
    cooldown = get_cooldown_remaining(pig.last_school_at, get_gameplay_settings().school_cooldown_minutes)
    if cooldown > 0:
        return redirect(url_for('pig.mon_cochon'))

    # Calculate performance
    # Example: 15 words, ideal time around 20-30s.
    # Score could be based on WPM
    wpm = (15 / time_taken) * 60 if time_taken > 0 else 0
    
    progression = get_progression_settings()
    typing_decay = get_learning_decay_multiplier(pig)
    typing_multiplier = progression.typing_stat_gain_multiplier * typing_decay
    xp_reward = int(round(progression.typing_xp_reward * typing_decay))

    if wpm > 40 and errors <= 2:
        vitesse_gain = round(1.5 * typing_multiplier, 2)
        agilite_gain = round(1.0 * typing_multiplier, 2)
        pig.vitesse = min(100, pig.vitesse + vitesse_gain)
        pig.agilite = min(100, pig.agilite + agilite_gain)
        bonus_msg = f"Excellent ! +{vitesse_gain:g} Vitesse, +{agilite_gain:g} Agilite."
        category = "success"
    elif wpm > 20:
        vitesse_gain = round(0.5 * typing_multiplier, 2)
        pig.vitesse = min(100, pig.vitesse + vitesse_gain)
        bonus_msg = f"Pas mal. +{vitesse_gain:g} Vitesse."
        category = "success"
    else:
        bonus_msg = "Tu peux faire mieux !"
        category = "warning"

    session_time = datetime.utcnow()
    pig.xp += xp_reward
    register_learning_session(pig, session_time=session_time)
    pig.reset_freshness()
    pig.mark_bad_state_if_needed()
    check_level_up(pig)
    db.session.commit()

    decay_msg = "" if typing_decay >= 0.999 else f" Rendement du jour: x{typing_decay:.2f}."
    flash(f"🏆 Typing Derby termine ! {bonus_msg} +{xp_reward} XP. (WPM: {wpm:.1f}, Erreurs: {errors}){decay_msg}", category)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'ok': True,
            'redirect_url': url_for('pig.mon_cochon'),
        })

    return redirect(url_for('pig.mon_cochon'))
