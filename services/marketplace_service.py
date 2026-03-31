from datetime import datetime
from extensions import db
from models import MarketplaceListing, InventoryItem

def create_listing(user_id, item_id, prix):
    """Crée une petite annonce pour Le Bon Groin."""
    inv_item = InventoryItem.query.filter_by(user_id=user_id, item_id=item_id).first()
    if not inv_item or inv_item.quantity < 1:
        return False, "Vous ne possédez pas cet objet."

    if prix <= 0:
        return False, "Le prix demande doit être supérieur à 0."

    listing = MarketplaceListing(
        seller_id=user_id,
        item_id=inv_item.id,
        prix_demande=prix,
        date_mise_en_vente=datetime.utcnow()
    )
    db.session.add(listing)

    # Réduire l'inventaire pour le bloquer (ou le retirer de l'inventaire actif)
    if inv_item.quantity == 1:
        db.session.delete(inv_item)
    else:
        inv_item.quantity -= 1

    db.session.commit()
    return True, "Annonce postée."

def get_all_listings():
    """Retourne toutes les annonces actives."""
    return MarketplaceListing.query.all()

def buy_from_marketplace(buyer_id, listing_id):
    """Achète un objet d'une petite annonce."""
    from models import User

    listing = MarketplaceListing.query.get(listing_id)
    if not listing:
        return False, "Annonce introuvable."

    buyer = User.query.get(buyer_id)
    if buyer_id == listing.seller_id:
        return False, "Vous ne pouvez pas acheter votre propre annonce."

    if not buyer.can_afford(listing.prix_demande):
        return False, "Fonds insuffisants en BitGroins."

    # Payer
    success = buyer.pay(listing.prix_demande, reason_code='marketplace_buy', reason_label=f"Achat sur Le Bon Groin", details=f"Objet: {listing.inventory_item.item.nom}")
    if not success:
        return False, "Erreur lors du paiement."

    # Gagner
    seller = User.query.get(listing.seller_id)
    if seller:
        seller.earn(listing.prix_demande, reason_code='marketplace_sell', reason_label=f"Vente sur Le Bon Groin", details=f"Objet: {listing.inventory_item.item.nom}")

    # Transferer propriete
    new_inv_item = InventoryItem.query.filter_by(user_id=buyer_id, item_id=listing.inventory_item.item_id).first()
    if new_inv_item:
        new_inv_item.quantity += 1
    else:
        new_inv_item = InventoryItem(user_id=buyer_id, item_id=listing.inventory_item.item_id, quantity=1)
        db.session.add(new_inv_item)

    # Supprimer l'annonce
    db.session.delete(listing)
    db.session.commit()
    
    return True, f"Achat de {listing.inventory_item.item.nom} réussi !"
