#!/usr/bin/env python3
import random

from app import create_app
from extensions import db
from models import Pig


def main():
    app = create_app()
    with app.app_context():
        pigs = Pig.query.all()
        if not pigs:
            print("Aucun cochon a mettre a jour.")
            return

        for pig in pigs:
            pig.sex = random.choice(['M', 'F'])

        db.session.commit()
        male_count = Pig.query.filter_by(sex='M').count()
        female_count = Pig.query.filter_by(sex='F').count()
        print(
            f"Sexes randomises pour {len(pigs)} cochons. "
            f"Males: {male_count}, Femelles: {female_count}."
        )


if __name__ == '__main__':
    main()
