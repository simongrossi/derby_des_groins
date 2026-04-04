from datetime import datetime

from extensions import db


class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    slogan = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    prix_truffes = db.Column(db.Float, default=0.0)
    prix_glands = db.Column(db.Float, default=0.0)
    type_effet = db.Column(db.String(50), nullable=True)
    valeur_effet = db.Column(db.Float, nullable=True)
    fiabilite = db.Column(db.Float, default=100.0)

    shop = db.relationship('Shop', backref=db.backref('items', lazy=True))


class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    user = db.relationship('User', backref=db.backref('inventory_items', lazy=True))
    item = db.relationship('Item')


class MarketplaceListing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    prix_demande = db.Column(db.Float, nullable=False)
    date_mise_en_vente = db.Column(db.DateTime, default=datetime.utcnow)

    seller = db.relationship('User', backref=db.backref('market_listings', lazy=True))
    inventory_item = db.relationship('InventoryItem')
