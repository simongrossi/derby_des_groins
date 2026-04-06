import os

from flask import render_template, request, redirect, url_for, flash, session

from exceptions import BusinessRuleError
from helpers.auth import admin_required
from models import User, Pig, PigAvatar
from services.admin_avatar_service import (
    create_avatar,
    delete_avatar,
    get_avatar_svg_code,
    update_avatar,
)
from services.admin_notification_service import get_smtp_config, send_email
from services.admin_pig_service import heal_admin_pig, toggle_admin_pig_life
from services.admin_user_service import (
    adjust_user_balance_by_admin,
    create_user_magic_link_token,
    reset_user_password,
    toggle_admin_status,
)
from routes.admin import admin_bp


# ══════════════════════════════════════════════════════════════════════════════
# Cochons
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/pigs')
@admin_required
def admin_pigs(user):
    pigs = Pig.query.order_by(Pig.is_alive.desc(), Pig.name.asc()).all()
    return render_template('admin_pigs.html', user=user, admin_tab='pigs', pigs=pigs)


@admin_bp.route('/admin/pigs/<int:pig_id>/toggle-life', methods=['POST'])
@admin_required
def admin_toggle_pig_life(user, pig_id):
    pig = Pig.query.get_or_404(pig_id)
    flash(toggle_admin_pig_life(pig), 'success')
    return redirect(url_for('admin.admin_pigs'))


@admin_bp.route('/admin/pigs/<int:pig_id>/heal', methods=['POST'])
@admin_required
def admin_heal_pig(user, pig_id):
    pig = Pig.query.get_or_404(pig_id)
    try:
        flash(heal_admin_pig(pig), "success")
    except BusinessRuleError as exc:
        flash(str(exc), "warning")
    return redirect(url_for('admin.admin_pigs'))


# ══════════════════════════════════════════════════════════════════════════════
# Joueurs
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/users')
@admin_required
def admin_users(user):
    users = User.query.order_by(User.username.asc()).all()
    magic_links = session.pop('_admin_magic_links', None)
    return render_template('admin_users.html',
        user=user, admin_tab='users', users=users, magic_links=magic_links)


@admin_bp.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def admin_toggle_user_admin(user, user_id):
    target = User.query.get_or_404(user_id)
    try:
        message = toggle_admin_status(user, target)
    except BusinessRuleError as exc:
        flash(str(exc), "error")
        return redirect(url_for('admin.admin_users'))

    flash(message, "success")
    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/admin/users/reset-password', methods=['POST'])
@admin_required
def admin_reset_password(user):
    user_id = request.form.get('user_id', type=int)
    new_password = request.form.get('new_password', '').strip()
    if not user_id:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for('admin.admin_users'))

    target = User.query.get_or_404(user_id)
    try:
        message = reset_user_password(target, new_password)
    except BusinessRuleError as exc:
        flash(str(exc), "error")
        return redirect(url_for('admin.admin_users'))

    flash(message, "success")
    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/admin/users/<int:user_id>/magic-link', methods=['POST'])
@admin_required
def admin_magic_link(user, user_id):
    target = User.query.get_or_404(user_id)
    magic_link = create_user_magic_link_token(target)
    token = magic_link['token']

    # Build the magic link URL (safe: url_for evite le Host header injection)
    base_url = os.environ.get('BASE_URL', '').rstrip('/')
    if base_url:
        magic_url = f"{base_url}/auth/magic/{token}"
    else:
        magic_url = url_for('auth.magic_login', token=token, _external=True)

    # Store in session for display
    links = session.get('_admin_magic_links', {})
    links[target.id] = magic_url
    session['_admin_magic_links'] = links

    flash(f"🔗 Lien magique genere pour {target.username} (24h).", "success")

    # Try to send by email if SMTP is configured and user has email
    if hasattr(target, 'email') and target.email:
        smtp_cfg = get_smtp_config()
        if smtp_cfg['enabled']:
            html = f"""
            <h2>🐷 Derby des Groins — Connexion magique</h2>
            <p>Salut <b>{target.username}</b> !</p>
            <p>Clique sur le lien ci-dessous pour te connecter automatiquement :</p>
            <p><a href="{magic_url}" style="background:#6366f1;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;">Se connecter</a></p>
            <p style="color:#888;font-size:12px;">Ce lien expire dans 24 heures.</p>
            """
            ok, err = send_email(target.email, 'Ton lien de connexion — Derby des Groins', html)
            if ok:
                flash(f"📧 Email envoye a {target.email}.", "success")
            else:
                flash(f"📧 Echec envoi email : {err}", "warning")

    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/admin/users/adjust-balance', methods=['POST'])
@admin_required
def admin_adjust_balance(user):
    user_id = request.form.get('user_id', type=int)
    amount = request.form.get('amount', type=float)
    reason = request.form.get('reason', 'Ajustement admin').strip()

    if not user_id:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for('admin.admin_users'))

    target = User.query.get_or_404(user_id)

    try:
        message = adjust_user_balance_by_admin(user, target, amount, reason)
    except BusinessRuleError as exc:
        flash(str(exc), "error")
        return redirect(url_for('admin.admin_users'))

    flash(message, "success")
    return redirect(url_for('admin.admin_users'))


# ══════════════════════════════════════════════════════════════════════════════
# Avatars
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/avatars')
@admin_required
def admin_avatars(user):
    avatars = PigAvatar.query.order_by(PigAvatar.name).all()
    return render_template('admin_avatars.html', user=user, admin_tab='avatars', avatars=avatars)


@admin_bp.route('/admin/avatars/upload', methods=['POST'])
@admin_required
def admin_avatar_upload(user):
    try:
        avatar = create_avatar(
            request.form.get('name', ''),
            request.form.get('svg_code', ''),
            request.files.get('avatar_file'),
        )
    except BusinessRuleError as exc:
        flash(str(exc), "error")
        return redirect(url_for('admin.admin_avatars'))

    flash(f"Avatar '{avatar.name}' ajoute.", "success")
    return redirect(url_for('admin.admin_avatars'))


@admin_bp.route('/admin/avatars/<int:avatar_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_avatar_edit(user, avatar_id):
    avatar = PigAvatar.query.get_or_404(avatar_id)

    if request.method == 'GET':
        svg_code = get_avatar_svg_code(avatar)
        return render_template('admin_avatar_edit.html', user=user, avatar=avatar, svg_code=svg_code)

    try:
        avatar = update_avatar(
            avatar,
            request.form.get('name', ''),
            request.form.get('svg_code', ''),
            request.files.get('avatar_file'),
        )
    except BusinessRuleError as exc:
        flash(str(exc), "error")
        return redirect(url_for('admin.admin_avatar_edit', avatar_id=avatar.id))

    flash(f"Avatar '{avatar.name}' mis a jour.", "success")
    return redirect(url_for('admin.admin_avatars'))


@admin_bp.route('/admin/avatars/<int:avatar_id>/delete', methods=['POST'])
@admin_required
def admin_avatar_delete(user, avatar_id):
    avatar = PigAvatar.query.get_or_404(avatar_id)
    name = delete_avatar(avatar)
    flash(f"Avatar '{name}' supprime.", "success")
    return redirect(url_for('admin.admin_avatars'))
