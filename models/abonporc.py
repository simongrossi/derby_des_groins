from datetime import datetime
from extensions import db

class AbonPorcTable(db.Model):
    __tablename__ = 'abonporc_table'

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='lobby', nullable=False) # lobby, voting, playing, finished
    phase = db.Column(db.String(20), default='recolte', nullable=True) # recolte, mecanique, livraison, entretien
    buy_in = db.Column(db.Integer, default=0, nullable=False)
    action_seat = db.Column(db.Integer, default=1)
    hand_number = db.Column(db.Integer, default=0)
    deck_json = db.Column(db.Text, default='[]')
    center_pigs_json = db.Column(db.Text, default='[]') # Cochons au centre de la table
    state_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    players = db.relationship('AbonPorcPlayer', backref='table', lazy=True, cascade='all, delete-orphan')

class AbonPorcPlayer(db.Model):
    __tablename__ = 'abonporc_player'

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('abonporc_table.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    seat = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='waiting')
    hand_json = db.Column(db.Text, default='[]') # Visible uniquement par le joueur
    vehicle_json = db.Column(db.Text, default='null') # Posé devant soi
    trailer_json = db.Column(db.Text, default='null') # Attaché au véhicule
    gray_card_json = db.Column(db.Text, default='null') # Attaché au véhicule
    victory_pigs_json = db.Column(db.Text, default='[]') # Zone de victoire
    larcins_json = db.Column(db.Text, default='[]') # Larcins subis
    vote = db.Column(db.Integer, nullable=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('abonporc_seats', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('table_id', 'seat', name='uq_abonporc_table_seat'),
    )
