from flask import Blueprint, render_template, redirect, url_for, session, flash, request, current_app
import time

from models import User
from services.history_page_service import build_history_page_context
from services.homepage_service import build_homepage_context
from services.rules_page_service import build_rules_page_context
from services.main_page_service import (
    build_classement_page_context,
    build_empty_classement_page_context,
)

main_bp = Blueprint('main', __name__)

# ── Cache classement (5 min TTL) ─────────────────────────────────────────
_classement_cache = {'data': None, 'ts': 0}
_CLASSEMENT_TTL = 300  # 5 minutes

@main_bp.route('/')
def index():
    context = build_homepage_context(session.get('user_id'))
    reward = context.pop('daily_reward', 0.0)
    if reward > 0:
        flash(
            f"🎁 Prime de pointage : Vous avez reçu {reward:.0f} 🪙 BitGroins pour votre première connexion de la journée !",
            "success",
        )
    return render_template('index.html', **context)


@main_bp.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    context = build_history_page_context(
        session['user_id'],
        request.args.get('u', type=int),
        request.args.getlist('bet_u'),
        request.args.getlist('tx_u'),
    )
    return render_template('history.html', **context)


@main_bp.route('/classement')
def classement():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])

    now = time.time()
    try:
        if _classement_cache['data'] and (now - _classement_cache['ts']) < _CLASSEMENT_TTL:
            classement_context = _classement_cache['data']
        else:
            classement_context = build_classement_page_context()
            _classement_cache['data'] = classement_context
            _classement_cache['ts'] = now
    except Exception:
        current_app.logger.exception("Erreur lors de la construction du classement")
        if _classement_cache['data']:
            classement_context = _classement_cache['data']
        else:
            classement_context = build_empty_classement_page_context()
            flash("Le classement est temporairement indisponible. Réessaie dans quelques minutes.", "warning")

    return render_template(
        'classement.html',
        user=user,
        active_page='classement',
        **classement_context,
    )


@main_bp.route('/regles')
def regles():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])

    return render_template(
        'regles.html',
        user=user,
        active_page='regles',
        **build_rules_page_context(),
    )


@main_bp.route('/legendes-pop')
def legendes_pop():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])

    pop_pigs = [
        {"name": "Porky Pig", "emoji": "🎩", "desc": "Le pionnier. A transformé un bégaiement en une carrière légendaire.", "category": "Stars du Marché"},
        {"name": "Miss Piggy", "emoji": "🎀", "desc": "Influenceuse avant Instagram. Mélange unique de glamour et de violence passive-agressive.", "category": "Stars du Marché"},
        {"name": "Peppa Pig", "emoji": "☔", "desc": "CEO d\u2019un empire mondial basé sur des grognements et des flaques de boue.", "category": "Stars du Marché"},
        {"name": "Porcinet", "emoji": "🧣", "desc": "12 kg de stress, mais validé émotionnellement par toute une génération.", "category": "Stars du Marché"},
        {"name": "Napoléon", "emoji": "👑", "desc": "Commence comme cochon, finit comme manager toxique (La Ferme des Animaux).", "category": "Niveau Dangereux"},
        {"name": "Porco Rosso", "emoji": "🛩️", "desc": "Pilote, philosophe, cochon. Trois problèmes complexes en un seul groin.", "category": "Niveau Dangereux"},
        {"name": "Cochons (Pink Floyd)", "emoji": "🎸", "desc": "Métaphore officielle des élites. Entrée validée par guitare électrique.", "category": "Niveau Dangereux"},
        {"name": "Tête de cochon", "emoji": "💀", "desc": "Quand un cochon mort devient plus charismatique que les humains (Sa Majesté des Mouches).", "category": "Niveau Dangereux"},
        {"name": "Cochon Minecraft", "emoji": "🧊", "desc": "Moyen de transport discutable. Existe principalement pour être transformé en côtelette.", "category": "Quotidien Suspect"},
        {"name": "Cochons Verts", "emoji": "🤢", "desc": "Ingénieurs en structures inefficaces (Angry Birds).", "category": "Quotidien Suspect"},
        {"name": "Hog Rider", "emoji": "🔨", "desc": "Un homme qui crie sur un cochon. Personne ne remet ça en question.", "category": "Quotidien Suspect"},
        {"name": "Hamm / Bayonne", "emoji": "🪙", "desc": "Tirelire cynique de Toy Story. Le seul qui comprend réellement l\u2019économie.", "category": "Quotidien Suspect"},
        {"name": "Nif-Nif, Naf-Naf & Nouf-Nouf", "emoji": "🏠", "desc": "Trois approches du BTP. Une seule résiste réellement au souffle du loup.", "category": "Patrimoine"},
        {"name": "Babe", "emoji": "🐑", "desc": "Le seul cochon avec un plan de carrière et une reconversion réussie.", "category": "Patrimoine"},
        {"name": "Wilbur", "emoji": "🕸️", "desc": "Sauvé par une araignée (Charlotte) meilleure en communication de crise que lui.", "category": "Patrimoine"},
        {"name": "Peter Pig", "emoji": "⚓", "desc": "Preuve que même chez Disney, certains cochons n\u2019ont pas percé.", "category": "Patrimoine"},
        {"name": "Petunia Pig", "emoji": "👒", "desc": "Love interest officielle. Un potentiel inexploité par les studios.", "category": "Secondaires"},
        {"name": "Piggy (Merrie Melodies)", "emoji": "🤡", "desc": "Version bêta de Porky Pig. A servi de crash-test pour l\u2019humour.", "category": "Secondaires"},
        {"name": "Arnold Ziffel", "emoji": "📺", "desc": "Cochon traité comme un humain complet. Personne ne pose de questions.", "category": "Secondaires"},
        {"name": "Pumbaa", "emoji": "🐗", "desc": "Techniquement un phacochère. Accepté dans la base pour raisons administratives.", "category": "Secondaires"},
    ]
    return render_template('legendes_pop.html', user=user, pop_pigs=pop_pigs)
