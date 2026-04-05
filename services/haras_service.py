"""Service pour Groin-der — marketplace P2P de géniteurs porcins."""

from exceptions import BusinessRuleError, InsufficientFundsError, ValidationError
from extensions import db
from models import Pig, User

HARAS_COMMISSION_RATE = 0.15   # 15 % → Tirelire Centrale
MIN_HARAS_PRICE = 20.0
MAX_HARAS_PRICE = 50_000.0


def _get_active_pig_count(user):
    return Pig.query.filter_by(user_id=user.id, is_alive=True).count()


def get_haras_listings():
    """Retourne tous les cochons actuellement listés au Haras, ordonnés par popularité."""
    return (
        Pig.query
        .filter_by(haras_listed=True)
        .join(User, Pig.user_id == User.id)
        .order_by(Pig.haras_services_count.desc(), Pig.id.desc())
        .all()
    )


def is_eligible_for_haras(pig):
    """Un cochon peut être listé s'il est vivant OU retraité dans le Haras des Légendes."""
    return pig.is_alive or pig.retired_into_heritage


def list_pig_in_haras(user, pig, price):
    """Liste un cochon au Haras Porcin.

    Args:
        user: Le propriétaire
        pig: Le cochon à lister
        price: Le prix de la saillie (BG)

    Returns:
        Le cochon mis à jour
    """
    if pig.user_id != user.id:
        raise BusinessRuleError("Ce cochon ne t'appartient pas.")
    if not is_eligible_for_haras(pig):
        raise BusinessRuleError("Ce cochon n'est pas éligible sur Groin-der (doit être vivant ou à la retraite honorée).")
    if pig.haras_listed:
        raise BusinessRuleError("Ce cochon a déjà un profil sur Groin-der.")

    try:
        price = round(float(price), 2)
    except (TypeError, ValueError):
        raise ValidationError("Le prix doit être un nombre valide.")

    if price < MIN_HARAS_PRICE:
        raise ValidationError(f"Le prix minimum de saillie est de {MIN_HARAS_PRICE:.0f} BG.")
    if price > MAX_HARAS_PRICE:
        raise ValidationError(f"Le prix maximum de saillie est de {MAX_HARAS_PRICE:.0f} BG.")

    pig.haras_listed = True
    pig.haras_price = price
    db.session.commit()
    return pig


def unlist_pig_from_haras(user, pig):
    """Retire un cochon du Haras Porcin."""
    if pig.user_id != user.id:
        raise BusinessRuleError("Ce cochon ne t'appartient pas.")
    if not pig.haras_listed:
        raise BusinessRuleError("Ce cochon n'a pas de profil sur Groin-der.")

    pig.haras_listed = False
    pig.haras_price = None
    db.session.commit()
    return pig


def perform_saillie(buyer, stud_pig, porcelet_name=None):
    """Effectue une saillie au Haras Porcin.

    Transaction :
    - L'acheteur paie le prix de saillie
    - Le propriétaire reçoit 85 %
    - 15 % vont à la Tirelire Centrale (frais de notaire porcin)
    - Un porcelet est créé pour l'acheteur, héritant des gènes du géniteur

    Returns:
        Le porcelet créé
    """
    from services.finance_service import debit_user, credit_user_balance
    from services.pig_lineage_service import create_offspring_from_stud
    from services.place_financiere_service import add_to_tirelire
    from services.pig_service import get_max_pig_slots, get_pig_slot_count

    # ── Validations ──────────────────────────────────────────────────────────
    if not stud_pig.haras_listed:
        raise BusinessRuleError("Ce cochon n'est plus disponible sur Groin-der.")
    if not is_eligible_for_haras(stud_pig):
        raise BusinessRuleError("Ce géniteur n'est plus éligible (mort sans retraite honorée).")
    if buyer.id == stud_pig.user_id:
        raise BusinessRuleError("Tu ne peux pas demander une saillie avec ton propre cochon !")

    stud_price = round(float(stud_pig.haras_price or 0.0), 2)
    if stud_price <= 0:
        raise BusinessRuleError("Ce cochon n'a pas de prix de saillie configuré.")

    # Vérification place disponible
    max_slots = get_max_pig_slots(buyer)
    used_slots = get_pig_slot_count(buyer)
    if used_slots >= max_slots:
        raise BusinessRuleError(
            f"Ta porcherie est pleine ({max_slots} cochons max). "
            "Fais de la place avant de demander une saillie !"
        )

    # ── Transaction financière ────────────────────────────────────────────────
    owner = db.session.get(User, stud_pig.user_id)
    owner_share = round(stud_price * (1.0 - HARAS_COMMISSION_RATE), 2)
    commission = round(stud_price - owner_share, 2)

    debit_user(
        buyer,
        stud_price,
        reason_code='haras_saillie',
        reason_label='Match Groin-der',
        details=f"Saillie avec {stud_pig.name} ({stud_pig.emoji}) de {owner.username if owner else '?'}.",
        reference_type='pig',
        reference_id=stud_pig.id,
        commit=False,
    )

    credit_user_balance(
        stud_pig.user_id,
        owner_share,
        reason_code='haras_sale',
        reason_label='Match vendu sur Groin-der',
        details=(
            f"Match de {stud_pig.name} ({stud_pig.emoji}) acheté par {buyer.username}. "
            f"Commission Groin-der : -{commission:.2f} BG (15 %)."
        ),
        reference_type='pig',
        reference_id=stud_pig.id,
    )

    add_to_tirelire(commission)

    # ── Création du porcelet ──────────────────────────────────────────────────
    porcelet = create_offspring_from_stud(buyer, stud_pig, name=porcelet_name)
    db.session.add(porcelet)

    stud_pig.haras_services_count = (stud_pig.haras_services_count or 0) + 1

    db.session.commit()
    return porcelet


def get_user_haras_eligible_pigs(user):
    """Retourne les cochons d'un joueur éligibles au listing Haras (non déjà listés)."""
    return [
        pig for pig in user.pigs
        if is_eligible_for_haras(pig) and not pig.haras_listed
    ]
