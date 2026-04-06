from flask import render_template, request, redirect, url_for, flash

from exceptions import BusinessRuleError
from helpers.auth import admin_required
from helpers.game_data import invalidate_game_data_cache
from models import CerealItem, TrainingItem, SchoolLessonItem, HangmanWordItem
from services.admin_game_data_service import (
    delete_cereal_item,
    delete_hangman_word,
    delete_lesson_item,
    delete_training_item,
    replace_hangman_words_from_text,
    save_cereal_item,
    save_hangman_word,
    save_lesson_item,
    save_training_item,
    toggle_cereal_item,
    toggle_hangman_word,
    toggle_lesson_item,
    toggle_training_item,
)
from routes.admin import admin_bp, STAT_NAMES


@admin_bp.after_request
def _invalidate_game_data_on_write(response):
    """Invalidate game data cache after any successful POST on /admin/data/*."""
    if (request.method == 'POST'
            and request.path.startswith('/admin/data/')
            and response.status_code in (200, 302)):
        invalidate_game_data_cache()
    return response


# ══════════════════════════════════════════════════════════════════════════════
# Donnees de jeu (CRUD cereales, entrainements, lecons, mots du pendu)
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/data')
@admin_required
def admin_data(user):
    cereals = CerealItem.query.order_by(CerealItem.sort_order, CerealItem.id).all()
    trainings = TrainingItem.query.order_by(TrainingItem.sort_order, TrainingItem.id).all()
    lessons = SchoolLessonItem.query.order_by(SchoolLessonItem.sort_order, SchoolLessonItem.id).all()
    hangman_words = HangmanWordItem.query.order_by(HangmanWordItem.sort_order, HangmanWordItem.id).all()
    hangman_words_text = '\n'.join(word.word for word in hangman_words)
    return render_template('admin_data.html',
        user=user, admin_tab='data', cereals=cereals, trainings=trainings, lessons=lessons,
        hangman_words=hangman_words, hangman_words_text=hangman_words_text,
        stat_names=STAT_NAMES)


# ── Cereales ──────────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/cereal/<int:item_id>', methods=['GET'])
@admin_required
def admin_cereal_edit(user, item_id):
    item = CerealItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='edit', item_type='cereal', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/cereal/new', methods=['GET'])
@admin_required
def admin_cereal_new(user):
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='new', item_type='cereal', item=None, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/cereal/save', methods=['POST'])
@admin_required
def admin_cereal_save(user):
    item_id = request.form.get('item_id', type=int)
    if item_id:
        item = CerealItem.query.get_or_404(item_id)
    else:
        item = CerealItem()

    try:
        item = save_cereal_item(request.form, item)
    except BusinessRuleError as exc:
        flash(str(exc), "error")
        return redirect(url_for('admin.admin_cereal_edit', item_id=item_id) if item_id else url_for('admin.admin_cereal_new'))

    flash(f"Cereale '{item.name}' sauvegardee !", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/cereal/<int:item_id>/delete', methods=['POST'])
@admin_required
def admin_cereal_delete(user, item_id):
    item = CerealItem.query.get_or_404(item_id)
    name = delete_cereal_item(item)
    flash(f"Cereale '{name}' supprimee.", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/cereal/<int:item_id>/toggle', methods=['POST'])
@admin_required
def admin_cereal_toggle(user, item_id):
    item = CerealItem.query.get_or_404(item_id)
    is_active = toggle_cereal_item(item)
    state = 'activee' if is_active else 'desactivee'
    flash(f"{item.emoji} {item.name} {state}.", "success")
    return redirect(url_for('admin.admin_data'))


# ── Entrainements ─────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/training/<int:item_id>', methods=['GET'])
@admin_required
def admin_training_edit(user, item_id):
    item = TrainingItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='edit', item_type='training', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/training/new', methods=['GET'])
@admin_required
def admin_training_new(user):
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='new', item_type='training', item=None, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/training/save', methods=['POST'])
@admin_required
def admin_training_save(user):
    item_id = request.form.get('item_id', type=int)
    if item_id:
        item = TrainingItem.query.get_or_404(item_id)
    else:
        item = TrainingItem()

    try:
        item = save_training_item(request.form, item)
    except BusinessRuleError as exc:
        flash(str(exc), "error")
        return redirect(url_for('admin.admin_training_edit', item_id=item_id) if item_id else url_for('admin.admin_training_new'))

    flash(f"Entrainement '{item.name}' sauvegarde !", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/training/<int:item_id>/delete', methods=['POST'])
@admin_required
def admin_training_delete(user, item_id):
    item = TrainingItem.query.get_or_404(item_id)
    name = delete_training_item(item)
    flash(f"Entrainement '{name}' supprime.", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/training/<int:item_id>/toggle', methods=['POST'])
@admin_required
def admin_training_toggle(user, item_id):
    item = TrainingItem.query.get_or_404(item_id)
    is_active = toggle_training_item(item)
    state = 'active' if is_active else 'desactive'
    flash(f"{item.emoji} {item.name} {state}.", "success")
    return redirect(url_for('admin.admin_data'))


# ── Lecons d'ecole ────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/lesson/<int:item_id>', methods=['GET'])
@admin_required
def admin_lesson_edit(user, item_id):
    item = SchoolLessonItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='edit', item_type='lesson', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/lesson/new', methods=['GET'])
@admin_required
def admin_lesson_new(user):
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='new', item_type='lesson', item=None, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/lesson/save', methods=['POST'])
@admin_required
def admin_lesson_save(user):
    item_id = request.form.get('item_id', type=int)
    if item_id:
        item = SchoolLessonItem.query.get_or_404(item_id)
    else:
        item = SchoolLessonItem()

    try:
        item = save_lesson_item(request.form, item)
    except BusinessRuleError as exc:
        flash(str(exc), "error")
        return redirect(url_for('admin.admin_lesson_edit', item_id=item_id) if item_id else url_for('admin.admin_lesson_new'))

    flash(f"Lecon '{item.name}' sauvegardee !", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/lesson/<int:item_id>/delete', methods=['POST'])
@admin_required
def admin_lesson_delete(user, item_id):
    item = SchoolLessonItem.query.get_or_404(item_id)
    name = delete_lesson_item(item)
    flash(f"Lecon '{name}' supprimee.", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/lesson/<int:item_id>/toggle', methods=['POST'])
@admin_required
def admin_lesson_toggle(user, item_id):
    item = SchoolLessonItem.query.get_or_404(item_id)
    is_active = toggle_lesson_item(item)
    state = 'activee' if is_active else 'desactivee'
    flash(f"{item.emoji} {item.name} {state}.", "success")
    return redirect(url_for('admin.admin_data'))


# ── Mots du Cochon Pendu ────────────────────────────────────────────────────

@admin_bp.route('/admin/data/hangman-word/<int:item_id>', methods=['GET'])
@admin_required
def admin_hangman_word_edit(user, item_id):
    item = HangmanWordItem.query.get_or_404(item_id)
    return render_template(
        'admin_data_form.html',
        user=user,
        admin_tab='data',
        mode='edit',
        item_type='hangman_word',
        item=item,
        stat_names=STAT_NAMES,
    )


@admin_bp.route('/admin/data/hangman-word/new', methods=['GET'])
@admin_required
def admin_hangman_word_new(user):
    return render_template(
        'admin_data_form.html',
        user=user,
        admin_tab='data',
        mode='new',
        item_type='hangman_word',
        item=None,
        stat_names=STAT_NAMES,
    )


@admin_bp.route('/admin/data/hangman-word/save', methods=['POST'])
@admin_required
def admin_hangman_word_save(user):
    item_id = request.form.get('item_id', type=int)
    redirect_target = (
        url_for('admin.admin_hangman_word_edit', item_id=item_id)
        if item_id else
        url_for('admin.admin_hangman_word_new')
    )

    if item_id:
        item = HangmanWordItem.query.get_or_404(item_id)
    else:
        item = HangmanWordItem()

    try:
        item = save_hangman_word(request.form, item)
    except BusinessRuleError as exc:
        category = "warning" if "lettres et des espaces" in str(exc) else "error"
        flash(str(exc), category)
        return redirect(redirect_target)
    flash(f"Mot '{item.word}' sauvegarde !", "success")
    return redirect(url_for('admin.admin_data') + '#hangman-words')


@admin_bp.route('/admin/data/hangman-words/bulk-save', methods=['POST'])
@admin_required
def admin_hangman_words_bulk_save(user):
    try:
        count = replace_hangman_words_from_text(request.form.get('words_text', ''))
    except BusinessRuleError as exc:
        flash(str(exc), "warning")
        return redirect(url_for('admin.admin_data') + '#hangman-words')

    flash(f"Liste du Cochon Pendu remplacee ({count} mots/expressions).", "success")
    return redirect(url_for('admin.admin_data') + '#hangman-words')


@admin_bp.route('/admin/data/hangman-word/<int:item_id>/delete', methods=['POST'])
@admin_required
def admin_hangman_word_delete(user, item_id):
    item = HangmanWordItem.query.get_or_404(item_id)
    word = delete_hangman_word(item)
    flash(f"Mot '{word}' supprime.", "success")
    return redirect(url_for('admin.admin_data') + '#hangman-words')


@admin_bp.route('/admin/data/hangman-word/<int:item_id>/toggle', methods=['POST'])
@admin_required
def admin_hangman_word_toggle(user, item_id):
    item = HangmanWordItem.query.get_or_404(item_id)
    is_active = toggle_hangman_word(item)
    state = 'active' if is_active else 'desactive'
    flash(f"Mot '{item.word}' {state}.", "success")
    return redirect(url_for('admin.admin_data') + '#hangman-words')
