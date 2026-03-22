from flask import Blueprint, render_template, session

from models import User
from helpers import get_dead_pigs_abattoir, get_legendary_pigs

abattoir_bp = Blueprint('abattoir', __name__)


@abattoir_bp.route('/abattoir')
def abattoir():
    dead_pigs = [p for p in get_dead_pigs_abattoir() if p.death_cause != 'vendu']
    total_dead = len(dead_pigs)
    most_common = {}
    for p in dead_pigs:
        t = p.charcuterie_type or 'Inconnu'
        most_common[t] = most_common.get(t, 0) + 1
    top_product = max(most_common, key=most_common.get) if most_common else None
    last_victim = dead_pigs[0] if dead_pigs else None
    return render_template('abattoir.html',
        dead_pigs=dead_pigs, total_dead=total_dead,
        top_product=top_product, last_victim=last_victim,
        user=User.query.get(session.get('user_id'))
    )


@abattoir_bp.route('/cimetiere')
def cimetiere():
    legends = get_legendary_pigs()
    all_dead = [p for p in get_dead_pigs_abattoir() if p.death_cause != 'vendu']
    return render_template('cimetiere.html',
        legends=legends, total_dead=len(all_dead), total_legends=len(legends),
        user=User.query.get(session.get('user_id'))
    )
