from flask import Blueprint, render_template, redirect, url_for, session, request, flash
from extensions import limiter
from models import User, Shop, Item, InventoryItem, MarketplaceListing
from services.galerie_service import get_all_shops, get_shop_by_slug, get_items_for_shop, get_item, buy_from_shop, init_shops
from services.marketplace_service import get_all_listings, create_listing, buy_from_marketplace

galerie_bp = Blueprint('galerie', __name__)

@galerie_bp.route('/galerie-lard-chande')
def galerie():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user = User.query.get(session['user_id'])
    init_shops() # On s'assure que les boutiques sont là
    shops = get_all_shops()
    return render_template('galerie_lard_chande.html', user=user, shops=shops, active_page='galerie')

@galerie_bp.route('/galerie-lard-chande/<slug>')
def shop_detail(slug):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user = User.query.get(session['user_id'])
    shop = get_shop_by_slug(slug)
    if not shop:
        return redirect(url_for('galerie.galerie'))
        
    items = get_items_for_shop(shop.id)
    return render_template('shop_detail.html', user=user, shop=shop, items=items, active_page='galerie')

@galerie_bp.route('/galerie-lard-chande/<slug>/buy/<int:item_id>', methods=['POST'])
@limiter.limit("10 per minute")
def buy_item(slug, item_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user = User.query.get(session['user_id'])
    item = get_item(item_id)
    if not item:
        return redirect(url_for('galerie.shop_detail', slug=slug))
        
    currency = request.form.get('currency', 'glands')
    success, message = buy_from_shop(user, item, currency)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('galerie.shop_detail', slug=slug))

@galerie_bp.route('/le-bon-groin')
def le_bon_groin():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user = User.query.get(session['user_id'])
    listings = get_all_listings()
    
    # Récupérer les items de l'utilisateur pour le formulaire de vente
    inventory_items = InventoryItem.query.filter_by(user_id=user.id).filter(InventoryItem.quantity > 0).all()
    
    return render_template('le_bon_groin.html', user=user, listings=listings, inventory_items=inventory_items, active_page='galerie')

@galerie_bp.route('/le-bon-groin/sell', methods=['POST'])
@limiter.limit("5 per minute")
def sell_marketplace():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user = User.query.get(session['user_id'])
    item_id = int(request.form.get('item_id', 0))
    prix = float(request.form.get('prix', 0))
    
    success, message = create_listing(user.id, item_id, prix)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('galerie.le_bon_groin'))

@galerie_bp.route('/le-bon-groin/buy/<int:listing_id>', methods=['POST'])
@limiter.limit("10 per minute")
def buy_marketplace(listing_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user = User.query.get(session['user_id'])
    success, message = buy_from_marketplace(user.id, listing_id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('galerie.le_bon_groin'))
