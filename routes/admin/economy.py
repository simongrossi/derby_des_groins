import json

from flask import render_template, request, redirect, url_for, flash, make_response

from config.economy_defaults import CASINO_REASON_CODES, TAX_EXEMPT_REASON_CODES
from config.grain_market_defaults import BOURSE_MOVEMENT_DIVISOR, BOURSE_SURCHARGE_FACTOR
from exceptions import BusinessRuleError
from helpers.auth import admin_required
from helpers.config import get_config
from services.economy_service import (
    build_admin_progression_context,
    build_admin_economy_context,
    build_day_reward_multipliers_from_form,
    build_economy_settings_from_form,
    build_progression_settings_from_form,
    build_progression_simulation_inputs_from_form,
    build_simulation_inputs_from_form,
    get_economy_settings,
    get_progression_settings,
    save_day_reward_multipliers,
    save_economy_settings,
    save_progression_settings,
)
from services.finance_service import (
    build_finance_settings_from_form,
    get_finance_settings,
    save_finance_settings,
)
from services.admin_settings_service import (
    save_admin_pig_settings,
    save_bourse_settings,
    save_race_engine_settings_json,
)
from services.game_settings_bundle_service import (
    build_game_settings_bundle_filename,
    build_game_settings_bundle_json,
    import_game_settings_bundle,
)
from services.gameplay_settings_service import (
    build_gameplay_settings_from_form,
    build_minigame_settings_from_form,
    get_gameplay_settings,
    get_minigame_settings,
    save_gameplay_settings,
    save_minigame_settings,
)
from services.pig_power_service import get_pig_settings
from services.race_engine_service import (
    get_race_engine_settings,
    reset_race_engine_settings,
)
from routes.admin import admin_bp


@admin_bp.route('/admin/economy', methods=['GET', 'POST'])
@admin_required
def admin_economy(user):
    current_settings = get_economy_settings()
    if request.method == 'POST':
        settings = build_economy_settings_from_form(request.form, current_settings=current_settings)
        reward_multiplier_overrides = build_day_reward_multipliers_from_form(request.form)
        preview_context = build_admin_economy_context(
            settings=settings,
            reward_multiplier_overrides=reward_multiplier_overrides,
        )
        simulation_inputs = build_simulation_inputs_from_form(
            request.form,
            preview_context['snapshot'],
            settings=settings,
        )
        if request.form.get('action') == 'save':
            save_economy_settings(settings)
            save_day_reward_multipliers(reward_multiplier_overrides)
            flash("Configuration economique sauvegardee.", "success")
            current_settings = settings
        context = build_admin_economy_context(
            settings=(current_settings if request.form.get('action') == 'save' else settings),
            simulation_inputs=simulation_inputs,
            reward_multiplier_overrides=(None if request.form.get('action') == 'save' else reward_multiplier_overrides),
        )
    else:
        context = build_admin_economy_context(settings=current_settings)

    return render_template(
        'admin_economy.html',
        user=user,
        admin_tab='economy',
        admin_page='economy',
        **context,
    )


@admin_bp.route('/admin/progression', methods=['GET', 'POST'])
@admin_required
def admin_progression(user):
    current_settings = get_progression_settings()
    if request.method == 'POST':
        settings = build_progression_settings_from_form(request.form, current_settings=current_settings)
        preview_context = build_admin_progression_context(settings=settings)
        simulation_inputs = build_progression_simulation_inputs_from_form(
            request.form,
            preview_context['snapshot'],
            settings=settings,
        )
        if request.form.get('action') == 'save':
            save_progression_settings(settings)
            flash("Configuration de progression sauvegardee.", "success")
            current_settings = settings
        context = build_admin_progression_context(
            settings=(current_settings if request.form.get('action') == 'save' else settings),
            simulation_inputs=simulation_inputs,
        )
    else:
        context = build_admin_progression_context(settings=current_settings)

    return render_template(
        'admin_economy.html',
        user=user,
        admin_tab='progression',
        admin_page='progression',
        **context,
    )


@admin_bp.route('/admin/balance', methods=['GET', 'POST'])
@admin_required
def admin_balance(user):
    finance = get_finance_settings()
    pig = get_pig_settings()
    engine = get_race_engine_settings()
    gameplay = get_gameplay_settings()
    minigames = get_minigame_settings()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_finance':
            finance = build_finance_settings_from_form(request.form, current_settings=finance)
            save_finance_settings(finance)
            flash("Paramètres financiers sauvegardés.", "success")

        elif action == 'save_pig':
            save_admin_pig_settings(request.form, pig)
            pig = get_pig_settings()
            flash("Paramètres cochons sauvegardés.", "success")

        elif action == 'save_gameplay':
            gameplay = build_gameplay_settings_from_form(request.form, gameplay)
            save_gameplay_settings(gameplay)
            flash("Paramètres gameplay sauvegardés.", "success")

        elif action == 'save_minigames':
            minigames = build_minigame_settings_from_form(request.form, minigames)
            save_minigame_settings(minigames)
            flash("Paramètres mini-jeux sauvegardés.", "success")

        elif action == 'save_engine':
            try:
                save_race_engine_settings_json(request.form.get('race_engine_json', ''))
                engine = get_race_engine_settings()
                flash("Moteur de course sauvegardé.", "success")
            except BusinessRuleError as exc:
                flash(str(exc), "error")

        elif action == 'import_settings_bundle':
            upload = request.files.get('settings_bundle_file')
            raw_bundle = (request.form.get('settings_bundle_json') or '').strip()
            if upload and upload.filename:
                raw_bundle = upload.read().decode('utf-8')
            try:
                import_game_settings_bundle(raw_bundle)
                flash("Bundle JSON importé et appliqué.", "success")
            except BusinessRuleError as exc:
                flash(str(exc), "error")

        elif action == 'reset_engine':
            reset_race_engine_settings()
            engine = get_race_engine_settings()
            flash("Moteur de course réinitialisé aux valeurs par défaut.", "success")

        elif action == 'save_bourse':
            try:
                save_bourse_settings(request.form)
                flash("Paramètres bourse sauvegardés.", "success")
            except BusinessRuleError as exc:
                flash(str(exc), "error")

        # Reload after save
        finance = get_finance_settings()
        pig = get_pig_settings()
        engine = get_race_engine_settings()
        gameplay = get_gameplay_settings()
        minigames = get_minigame_settings()

    return render_template(
        'admin_balance.html',
        user=user,
        admin_tab='balance',
        finance=finance,
        pig=pig,
        pig_weight_rules_json=json.dumps(pig.weight_rules.__dict__, ensure_ascii=False, indent=2),
        gameplay=gameplay,
        minigames=minigames,
        engine_json=engine.to_json(),
        settings_bundle_json=build_game_settings_bundle_json(),
        bourse_surcharge_factor=float(get_config('bourse_surcharge_factor', str(BOURSE_SURCHARGE_FACTOR))),
        bourse_movement_divisor=int(float(get_config('bourse_movement_divisor', str(BOURSE_MOVEMENT_DIVISOR)))),
        tax_exempt_codes=sorted(TAX_EXEMPT_REASON_CODES),
        casino_reason_codes=sorted(CASINO_REASON_CODES),
    )


@admin_bp.route('/admin/settings-bundle/export')
@admin_required
def admin_export_settings_bundle(user):
    response = make_response(build_game_settings_bundle_json())
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="{build_game_settings_bundle_filename()}"'
    return response
