from extensions import db
from models import Shop, Item

SHOPS_DATA = [
    {
        'nom': "Decat'Lard",
        'slug': 'decat-lard',
        'slogan': 'À fond la forme, à fond le gras',
        'description': 'Équipements sportifs pour cochons athlètes.',
        'items': [
            {'nom': 'Air-Lardon 1', 'description': 'Chaussures aérodynamiques pour courir plus vite.', 'prix_glands': 150, 'prix_truffes': 10, 'type_effet': 'vitesse', 'valeur_effet': 5, 'fiabilite': 95},
            {'nom': 'Graisse à Traire Aérodynamique', 'description': 'Réduit les frottements d\'air.', 'prix_glands': 80, 'prix_truffes': 5, 'type_effet': 'vitesse', 'valeur_effet': 2, 'fiabilite': 100},
        ]
    },
    {
        'nom': 'La Fnac-uterie',
        'slug': 'fnac-uterie',
        'slogan': 'Fédération Nationale des Amateurs de Charcuterie',
        'description': 'Culture, Geek et accessoires improbables.',
        'items': [
            {'nom': 'Figurine du Fantôme Gris', 'description': 'Rend invincible lors de la prochaine course.', 'prix_glands': 300, 'prix_truffes': 20, 'type_effet': 'invulnerabilite', 'valeur_effet': 1, 'fiabilite': 100},
            {'nom': 'Disque Vinyle Édition Limitée', 'description': 'Beats lo-fi pour détendre votre cochon.', 'prix_glands': 120, 'prix_truffes': 8, 'type_effet': 'moral', 'valeur_effet': 10, 'fiabilite': 100},
        ]
    },
    {
        'nom': 'Le Porc-Shop',
        'slug': 'porc-shop',
        'slogan': 'Retouchez la réalité',
        'description': 'Cosmétiques et effets visuels pour briller.',
        'items': [
            {'nom': 'Sourire du Joker-Bon', 'description': 'Terrifiez vos adversaires (baisse leur moral).', 'prix_glands': 200, 'prix_truffes': 15, 'type_effet': 'terreur', 'valeur_effet': -5, 'fiabilite': 90},
            {'nom': 'Objectif R-Porc Mark II', 'description': 'Éblouissez le public pour plus de popularité.', 'prix_glands': 250, 'prix_truffes': 18, 'type_effet': 'gloire', 'valeur_effet': 8, 'fiabilite': 85},
        ]
    },
    {
        'nom': 'Amagroin',
        'slug': 'amagroin',
        'slogan': 'Livraison Prime dans l\'auge',
        'description': 'Consommables premium livrés rapidement.',
        'items': [
            {'nom': 'Sérum de Rillettes du Mans', 'description': 'Soin complet et immédiat.', 'prix_glands': 400, 'prix_truffes': 30, 'type_effet': 'soin_total', 'valeur_effet': 100, 'fiabilite': 100},
            {'nom': 'Cape de Bat-Cochon', 'description': 'Augmente l\'agilité en pleine nuit.', 'prix_glands': 180, 'prix_truffes': 12, 'type_effet': 'agilite', 'valeur_effet': 6, 'fiabilite': 95},
        ]
    },
    {
        'nom': 'AliGoret',
        'slug': 'aligoret',
        'slogan': 'Pas cher, mais ça casse',
        'description': 'Des objets à bas prix mais à vos risques et périls.',
        'items': [
            {'nom': 'Casque en Briques Contrefait', 'description': 'Protection minime mais pas cher.', 'prix_glands': 20, 'prix_truffes': 1, 'type_effet': 'armure', 'valeur_effet': 2, 'fiabilite': 30},
            {'nom': 'Collier de Saucisses périmées', 'description': 'Nourrit, mais risque d\'indigestion massif.', 'prix_glands': 10, 'prix_truffes': 0, 'type_effet': 'faim', 'valeur_effet': 50, 'fiabilite': 15},
        ]
    }
]

def init_shops():
    """Initialise les boutiques et leurs objets si la galerie est vide."""
    if Shop.query.first():
        return

    for shop_data in SHOPS_DATA:
        shop = Shop(
            nom=shop_data['nom'],
            slug=shop_data['slug'],
            slogan=shop_data['slogan'],
            description=shop_data['description']
        )
        db.session.add(shop)
        db.session.flush()

        for item_data in shop_data['items']:
            item = Item(
                shop_id=shop.id,
                nom=item_data['nom'],
                description=item_data['description'],
                prix_glands=item_data['prix_glands'],
                prix_truffes=item_data['prix_truffes'],
                type_effet=item_data['type_effet'],
                valeur_effet=item_data['valeur_effet'],
                fiabilite=item_data['fiabilite']
            )
            db.session.add(item)
    
    db.session.commit()

def get_all_shops():
    return Shop.query.all()

def get_shop_by_slug(slug):
    return Shop.query.filter_by(slug=slug).first()

def get_items_for_shop(shop_id):
    return Item.query.filter_by(shop_id=shop_id).all()

def get_item(item_id):
    return Item.query.get(item_id)

def buy_from_shop(user, item, currency):
    """
    Achète un objet dans la boutique.
    Retourne (succès: bool, message: str)
    """
    from models import InventoryItem
    
    prix = item.prix_truffes if currency == 'truffes' else item.prix_glands
    if prix < 0:
        return False, "Prix invalide."

    # Si c'est des glands, c'est payé avec le solde BitGroins
    # Si c'est des truffes, on suppose que l'utilisateur n'a pas encore de truffes, mais on va déduire de user.truffes_balance
    if currency == 'glands':
        if not user.can_afford(prix):
            return False, "Fonds insuffisants en BitGroins (Glands)."
        # Déduire l'argent
        success = user.pay(prix, reason_code='shop_buy', reason_label=f"Achat: {item.nom}", details=f"Achats Galeries Lard-Chande")
        if not success:
            return False, "Erreur lors du paiement."
    elif currency == 'truffes':
        # On essaie d'utiliser user.truffes_balance s'il existe (à implémenter si ce n'est pas le cas)
        truffes_balance = getattr(user, 'truffes_balance', 0.0)
        if truffes_balance < prix:
            return False, "Fonds insuffisants en Truffes."
        user.truffes_balance -= prix
        db.session.commit()
    else:
        return False, "Monnaie non reconnue."

    # Ajouter à l'inventaire
    inv_item = InventoryItem.query.filter_by(user_id=user.id, item_id=item.id).first()
    if inv_item:
        inv_item.quantity += 1
    else:
        inv_item = InventoryItem(user_id=user.id, item_id=item.id, quantity=1)
        db.session.add(inv_item)
    
    db.session.commit()
    return True, f"Vous avez acheté {item.nom} avec succès !"
