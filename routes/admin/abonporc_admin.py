from flask import render_template, flash, redirect, url_for, request
from extensions import db
from helpers.auth import admin_required
from models import AbonPorcTable, AbonPorcPlayer, User
from services.finance_service import credit_user_balance
from routes.admin import admin_bp

@admin_bp.route('/abonporc_games')
@admin_required
def abonporc_games(user):

    active_tables = AbonPorcTable.query.filter(AbonPorcTable.status.in_(['lobby', 'voting', 'playing'])).all()
    
    tables_data = []
    for table in active_tables:
        players = AbonPorcPlayer.query.filter_by(table_id=table.id).all()
        players_info = []
        for player in players:
            user = User.query.get(player.user_id)
            players_info.append({
                'username': user.username if user else 'Inconnu',
                'seat': player.seat,
                'vote': player.vote,
                'status': player.status
            })
        tables_data.append({
            'id': table.id,
            'status': table.status,
            'phase': table.phase,
            'buy_in': table.buy_in,
            'player_count': len(players),
            'players': players_info
        })

    return render_template('admin/abonporc_games.html', tables=tables_data)

@admin_bp.route('/abonporc_games/reset', methods=['POST'])
@admin_required
def abonporc_games_reset(user):

    table_id = request.form.get('table_id')
    if table_id:
        table = AbonPorcTable.query.get(table_id)
        if not table:
            flash(f"Table A Bon Porc #{table_id} non trouvée.", "warning")
            return redirect(url_for('admin.abonporc_games'))
        tables_to_reset = [table]
    else:
        tables_to_reset = AbonPorcTable.query.filter(AbonPorcTable.status.in_(['lobby', 'voting', 'playing'])).all()

    count_reset = 0
    for table_to_reset in tables_to_reset:
        players = AbonPorcPlayer.query.filter_by(table_id=table_to_reset.id).all()
        for player in players:
            if table_to_reset.buy_in > 0:
                credit_user_balance(
                    player.user_id,
                    table_to_reset.buy_in,
                    reason_code='abonporc_admin_refund',
                    reason_label=f'Remboursement admin A Bon Porc (Table #{table_to_reset.id})'
                )
                flash(f"Remboursement de {table_to_reset.buy_in} 🪙 à {User.query.get(player.user_id).username} pour la table #{table_to_reset.id}.", "info")
            db.session.delete(player)
        db.session.delete(table_to_reset)
        count_reset += 1

    db.session.commit()
    flash(f"{count_reset} table(s) A Bon Porc réinitialisée(s) et joueurs remboursés.", "success")
    return redirect(url_for('admin.abonporc_games'))
