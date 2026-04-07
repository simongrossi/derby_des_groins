from flask import Blueprint, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from extensions import db
from models import AbonPorcTable, AbonPorcPlayer, PokerTable, PokerPlayer, User
from services.finance_service import credit_user_balance

admin_game_bp = Blueprint('admin_game', __name__, url_prefix='/admin/games')

@admin_game_bp.before_request
@login_required
def admin_game_before_request():
    if not current_user.is_admin:
        flash("Accès non autorisé.", "danger")
        return redirect(url_for('main.index'))

@admin_game_bp.route('/reset-all', methods=['POST'])
def reset_all_games():
    """Réinitialise toutes les parties en cours (AbonPorc et Poker) et rembourse les joueurs."""
    
    # --- Réinitialisation des parties AbonPorc ---
    abonporc_tables = AbonPorcTable.query.filter(AbonPorcTable.status.in_(['lobby', 'voting', 'playing'])).all()
    abonporc_count = 0
    abonporc_refunds = {}

    for table in abonporc_tables:
        players = AbonPorcPlayer.query.filter_by(table_id=table.id).all()
        for player in players:
            if table.buy_in > 0:
                credit_user_balance(player.user_id, table.buy_in, 
                                    reason_code='admin_refund_abonporc', 
                                    reason_label=f'Remboursement admin AbonPorc Table #{table.id}',
                                    details=f'Remboursement du buy-in de {table.buy_in} BG suite annulation admin de la table #{table.id}')
                abonporc_refunds[player.user_id] = abonporc_refunds.get(player.user_id, 0) + table.buy_in
            db.session.delete(player)
        db.session.delete(table)
        abonporc_count += 1
    
    # --- Réinitialisation des parties Poker ---
    poker_tables = PokerTable.query.filter(PokerTable.status.in_(['lobby', 'voting', 'playing'])).all()
    poker_count = 0
    poker_refunds = {}

    for table in poker_tables:
        players = PokerPlayer.query.filter_by(table_id=table.id).all()
        for player in players:
            # Rembourser le buy-in initial si la partie n'a pas commencé ou les jetons restants
            amount_to_refund = player.chips if table.status == 'playing' else table.buy_in
            if amount_to_refund > 0:
                credit_user_balance(player.user_id, amount_to_refund, 
                                    reason_code='admin_refund_poker', 
                                    reason_label=f'Remboursement admin Poker Table #{table.id}',
                                    details=f'Remboursement de {amount_to_refund} BG suite annulation admin de la table #{table.id}')
                poker_refunds[player.user_id] = poker_refunds.get(player.user_id, 0) + amount_to_refund
            db.session.delete(player)
        db.session.delete(table)
        poker_count += 1

    db.session.commit()

    msg = f"Réinitialisation terminée : {abonporc_count} tables AbonPorc et {poker_count} tables Poker annulées."
    if abonporc_refunds or poker_refunds:
        msg += " Remboursements effectués."
    
    flash(msg, "success")
    current_app.logger.info(f"Admin {current_user.username} reset all games. AbonPorc: {abonporc_count} tables, Poker: {poker_count} tables. Refunds: AbonPorc={abonporc_refunds}, Poker={poker_refunds}")
    
    return jsonify({'success': True, 'message': msg})
