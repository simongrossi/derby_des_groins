from flask import render_template, request, redirect, url_for, flash, make_response

from content.stats_metadata import JOURS_FR
from exceptions import BusinessRuleError
from helpers.auth import admin_required
from models import Race, Bet
from services.admin_bet_service import (
    build_admin_bets_page_context,
    reconcile_bet_by_id,
    reconcile_finished_bets,
)
from services.admin_event_service import trigger_admin_event
from services.admin_notification_service import (
    get_smtp_config,
    save_smtp_settings,
    send_test_smtp_email,
)
from services.admin_race_service import (
    build_admin_races_page_context,
    cancel_race_and_refund_bets,
    export_race_npcs_csv_content,
    force_race_now,
    import_race_npcs_csv,
    save_admin_races_configuration,
)
from services.admin_truffes_service import (
    build_admin_truffes_context,
    save_truffes_settings,
)
from routes.admin import admin_bp


def _parse_race_npcs_from_lines(lines):
    """Normalise une liste de lignes 'Nom|Emoji' en liste de dicts."""
    npcs = []
    seen = set()
    for raw_line in lines:
        line = (raw_line or '').strip()
        if not line:
            continue
        if '|' in line:
            name_part, emoji_part = line.split('|', 1)
            name = name_part.strip()
            emoji = emoji_part.strip() or '🐷'
        else:
            name = line
            emoji = '🐷'
        if not name or name in seen:
            continue
        seen.add(name)
        npcs.append({'name': name, 'emoji': emoji})
    return npcs


# ══════════════════════════════════════════════════════════════════════════════
# Courses
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/races')
@admin_required
def admin_races(user):
    context = build_admin_races_page_context()
    return render_template(
        'admin_races.html',
        user=user,
        admin_tab='races',
        jours=JOURS_FR,
        **context,
    )


@admin_bp.route('/admin/save', methods=['POST'])
@admin_required
def admin_save(user):
    try:
        messages = save_admin_races_configuration(request.form)
    except BusinessRuleError as exc:
        flash(str(exc), "error")
        return redirect(url_for('admin.admin_races'))

    for message, category in messages:
        flash(message, category)
    return redirect(url_for('admin.admin_races'))


@admin_bp.route('/admin/races/npcs/export')
@admin_required
def admin_export_race_npcs_csv(user):
    """Exporte les PNJ de remplissage en CSV (name,emoji)."""
    response = make_response(export_race_npcs_csv_content())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename=race_npcs.csv'
    return response


@admin_bp.route('/admin/races/npcs/import', methods=['POST'])
@admin_required
def admin_import_race_npcs_csv(user):
    """Importe les PNJ de remplissage depuis un CSV (name,emoji)."""
    try:
        npc_count = import_race_npcs_csv(request.files.get('race_npcs_csv'))
    except BusinessRuleError as exc:
        message = str(exc)
        category = 'warning' if 'Aucun fichier' in message or 'Import vide' in message else 'error'
        flash(message, category)
        return redirect(url_for('admin.admin_races'))

    flash(f"Import CSV reussi: {npc_count} PNJ enregistres.", "success")
    return redirect(url_for('admin.admin_races'))


@admin_bp.route('/admin/force-race', methods=['POST'])
@admin_required
def admin_force_race(user):
    force_race_now()
    flash("🏁 Course forcee ! Resultats disponibles.", "success")
    return redirect(url_for('admin.admin_races'))


@admin_bp.route('/admin/races/<int:race_id>/cancel', methods=['POST'])
@admin_required
def admin_cancel_race(user, race_id):
    race = Race.query.get_or_404(race_id)
    try:
        cancelled_race_id = cancel_race_and_refund_bets(race)
    except BusinessRuleError as exc:
        flash(str(exc), "error")
        return redirect(url_for('admin.admin_races'))

    flash(f"Course #{cancelled_race_id} annulee et paris rembourses.", "success")
    return redirect(url_for('admin.admin_races'))


# ══════════════════════════════════════════════════════════════════════════════
# Paris
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/bets')
@admin_required
def admin_bets(user):
    context = build_admin_bets_page_context(
        status_filter=(request.args.get('status') or '').strip(),
        race_id_filter=request.args.get('race_id', type=int),
        username_filter=(request.args.get('username') or '').strip(),
        mismatch_only=request.args.get('mismatch') == '1',
    )
    return render_template(
        'admin_bets.html',
        user=user,
        admin_tab='bets',
        **context,
    )


@admin_bp.route('/admin/bets/reconcile', methods=['POST'])
@admin_required
def admin_reconcile_bets(user):
    updated = reconcile_finished_bets()
    flash(f"{updated} ticket(s) ont ete recalcules et corriges.", "success")
    return redirect(url_for('admin.admin_bets'))


@admin_bp.route('/admin/bets/<int:bet_id>/reconcile', methods=['POST'])
@admin_required
def admin_reconcile_bet(user, bet_id):
    bet, did_update, result = reconcile_bet_by_id(bet_id)
    if bet is None:
        flash(result, "error")
        return redirect(url_for('admin.admin_bets'))
    if not did_update:
        flash(result, "warning")
        return redirect(url_for('admin.admin_bets'))

    flash(f"Ticket #{bet.id} recalcule: statut final {result}.", "success")
    return redirect(url_for('admin.admin_bets'))


# ══════════════════════════════════════════════════════════════════════════════
# Evenements
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/events')
@admin_required
def admin_events(user):
    return render_template('admin_events.html', user=user, admin_tab='events')


@admin_bp.route('/admin/events/trigger', methods=['POST'])
@admin_required
def admin_trigger_event(user):
    try:
        message, category = trigger_admin_event(user, request.form.get('event_type'))
        flash(message, category)
    except BusinessRuleError as exc:
        flash(str(exc), "error")

    return redirect(url_for('admin.admin_events'))


# ══════════════════════════════════════════════════════════════════════════════
# Notifications SMTP
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/notifications')
@admin_required
def admin_notifications(user):
    smtp = get_smtp_config()
    return render_template('admin_notifications.html',
        user=user, admin_tab='notifications', smtp=smtp)


@admin_bp.route('/admin/notifications/save', methods=['POST'])
@admin_required
def admin_save_smtp(user):
    flash(save_smtp_settings(request.form), "success")
    return redirect(url_for('admin.admin_notifications'))


@admin_bp.route('/admin/notifications/test', methods=['POST'])
@admin_required
def admin_test_smtp(user):
    try:
        message, category = send_test_smtp_email(request.form.get('test_email', ''))
        flash(message, category)
    except BusinessRuleError as exc:
        flash(str(exc), "error")

    return redirect(url_for('admin.admin_notifications'))


# ══════════════════════════════════════════════════════════════════════════════
# Truffes
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/truffes', methods=['GET', 'POST'])
@admin_required
def admin_truffes(user):
    if request.method == 'POST':
        flash(save_truffes_settings(request.form), "success")
        return redirect(url_for('admin.admin_truffes'))

    return render_template(
        'admin_truffes.html',
        user=user,
        admin_tab='truffes',
        config=build_admin_truffes_context(),
    )
