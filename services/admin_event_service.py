from exceptions import ValidationError
from extensions import db
from models import Pig, User
from services.finance_service import credit_user

ADMIN_GLOBAL_GIFT_AMOUNT = 50.0
ADMIN_FOOD_DROP_DELTA = 30


def trigger_admin_event(actor, event_type):
    event_type = (event_type or '').strip()

    if event_type == 'food_drop':
        all_pigs = Pig.query.filter_by(is_alive=True).all()
        for pig in all_pigs:
            pig.energy = min(100, (pig.energy or 0) + ADMIN_FOOD_DROP_DELTA)
            pig.hunger = min(100, (pig.hunger or 0) + ADMIN_FOOD_DROP_DELTA)
        db.session.commit()
        return "📦 Distribution de nourriture ! +30 Energie/Faim pour tous.", "success"

    if event_type == 'vet_visit':
        injured_pigs = Pig.query.filter_by(is_alive=True, is_injured=True).all()
        for pig in injured_pigs:
            pig.heal()
        db.session.commit()
        return f"🏥 Visite veterinaire ! {len(injured_pigs)} groins soignes.", "success"

    if event_type == 'bonus_bg':
        all_users = User.query.all()
        for user in all_users:
            credit_user(
                user,
                ADMIN_GLOBAL_GIFT_AMOUNT,
                reason_code='admin_gift',
                reason_label='Cadeau Admin',
                reference_type='user',
                reference_id=actor.id,
                commit=False,
            )
        db.session.commit()
        return "💰 Bonus de 50 🪙 BitGroins accorde a tous !", "success"

    raise ValidationError("Evenement inconnu.")
