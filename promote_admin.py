import os
from app import create_app
from extensions import db
from models import User

def promote_user(username):
    app = create_app()
    # On force le chargement de la config de prod si on est dans docker
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user:
            user.is_admin = True
            db.session.commit()
            print(f"✅ L'utilisateur '{username}' est maintenant administrateur.")
        else:
            print(f"❌ Utilisateur '{username}' introuvable dans la base de données.")

if __name__ == "__main__":
    # On peut changer le nom ici si besoin
    target_username = "Christophe"
    promote_user(target_username)
