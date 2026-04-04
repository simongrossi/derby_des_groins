from datetime import datetime

from exceptions import ValidationError
from extensions import db


def toggle_admin_pig_life(pig):
    pig.is_alive = not pig.is_alive
    if pig.is_alive:
        pig.death_date = None
        pig.death_cause = None
        pig.charcuterie_type = None
        pig.charcuterie_emoji = None
        pig.epitaph = None
    else:
        pig.death_date = datetime.utcnow()
        pig.death_cause = pig.death_cause or 'admin'

    db.session.commit()
    return f"Statut mis a jour pour {pig.name}."


def heal_admin_pig(pig):
    if not pig.is_injured:
        raise ValidationError(f"{pig.name} n'est pas blesse.")

    pig.heal()
    db.session.commit()
    return f"🏥 {pig.name} a ete soigne !"
