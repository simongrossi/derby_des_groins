from types import SimpleNamespace
import unittest
from unittest.mock import patch

from exceptions import ValidationError
from extensions import db
from models import Pig, User
from services.pig_lineage_service import (
    build_pig_lineage_tree,
    build_unique_pig_name,
    create_offspring,
    get_pig_heritage_value,
    is_pig_name_taken,
    normalize_pig_name,
)
from tests.support import build_test_app, reset_database


class PigLineageServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)

    def test_build_pig_lineage_tree_returns_ancestors_and_descendants(self):
        with self.app.app_context():
            owner = User(username='Owner', password_hash='x')
            db.session.add(owner)
            db.session.flush()

            sire = Pig(user_id=owner.id, name='Sire', sex='M', generation=1, lineage_name='Maison Sire')
            dam = Pig(user_id=owner.id, name='Dam', sex='F', generation=1, lineage_name='Maison Dam')
            db.session.add_all([sire, dam])
            db.session.flush()

            focus = Pig(
                user_id=owner.id,
                name='Focus',
                sex='M',
                generation=2,
                lineage_name='Maison Focus',
                sire_id=sire.id,
                dam_id=dam.id,
            )
            db.session.add(focus)
            db.session.flush()

            child = Pig(
                user_id=owner.id,
                name='Child',
                sex='F',
                generation=3,
                lineage_name='Maison Focus',
                sire_id=focus.id,
            )
            db.session.add(child)
            db.session.commit()

            payload = build_pig_lineage_tree(focus.id, max_depth=4)

        self.assertIsNotNone(payload)
        self.assertEqual('Focus', payload['focus']['name'])
        self.assertEqual(2, payload['meta']['ancestor_count'])
        self.assertEqual(1, payload['meta']['descendant_count'])
        self.assertEqual({'Sire', 'Dam'}, {node['name'] for node in payload['focus']['parents']})
        self.assertEqual('Child', payload['focus']['children'][0]['name'])

    def test_lineage_tree_route_returns_json_for_owned_pig(self):
        with self.app.app_context():
            owner = User(username='Viewer', password_hash='x')
            db.session.add(owner)
            db.session.flush()
            pig = Pig(user_id=owner.id, name='Viewer Pig', sex='M', generation=1, lineage_name='Maison Viewer')
            db.session.add(pig)
            db.session.commit()
            owner_id = owner.id
            pig_id = pig.id

        client = self.app.test_client()
        with client.session_transaction() as session:
            session['user_id'] = owner_id

        response = client.get(f'/api/pigs/{pig_id}/lineage-tree?depth=3')
        payload = response.get_json()

        self.assertEqual(200, response.status_code)
        self.assertEqual('Viewer Pig', payload['focus']['name'])
        self.assertEqual(3, payload['meta']['max_depth'])

    def test_lineage_tree_route_allows_public_haras_listed_pig(self):
        with self.app.app_context():
            owner = User(username='HarasOwner', password_hash='x')
            viewer = User(username='HarasViewer', password_hash='x')
            db.session.add_all([owner, viewer])
            db.session.flush()
            pig = Pig(
                user_id=owner.id,
                name='Etalon Public',
                sex='M',
                generation=2,
                lineage_name='Maison Publique',
                haras_listed=True,
            )
            db.session.add(pig)
            db.session.commit()
            viewer_id = viewer.id
            pig_id = pig.id

        client = self.app.test_client()
        with client.session_transaction() as session:
            session['user_id'] = viewer_id

        response = client.get(f'/api/pigs/{pig_id}/lineage-tree')
        payload = response.get_json()

        self.assertEqual(200, response.status_code)
        self.assertEqual('Etalon Public', payload['focus']['name'])

    def test_lineage_tree_route_allows_dead_legend_for_other_users(self):
        with self.app.app_context():
            owner = User(username='LegendOwner', password_hash='x')
            viewer = User(username='LegendViewer', password_hash='x')
            db.session.add_all([owner, viewer])
            db.session.flush()
            pig = Pig(
                user_id=owner.id,
                name='Legende',
                sex='F',
                generation=3,
                lineage_name='Maison Legende',
                is_alive=False,
                death_cause='challenge',
            )
            db.session.add(pig)
            db.session.commit()
            viewer_id = viewer.id
            pig_id = pig.id

        client = self.app.test_client()
        with client.session_transaction() as session:
            session['user_id'] = viewer_id

        response = client.get(f'/api/pigs/{pig_id}/lineage-tree')
        payload = response.get_json()

        self.assertEqual(200, response.status_code)
        self.assertEqual('Legende', payload['focus']['name'])

    def test_lineage_tree_route_forbids_private_active_pig_for_non_owner(self):
        with self.app.app_context():
            owner = User(username='PrivateOwner', password_hash='x')
            viewer = User(username='PrivateViewer', password_hash='x')
            db.session.add_all([owner, viewer])
            db.session.flush()
            pig = Pig(
                user_id=owner.id,
                name='Prive',
                sex='M',
                generation=1,
                lineage_name='Maison Privee',
                haras_listed=False,
                is_alive=True,
            )
            db.session.add(pig)
            db.session.commit()
            viewer_id = viewer.id
            pig_id = pig.id

        client = self.app.test_client()
        with client.session_transaction() as session:
            session['user_id'] = viewer_id

        response = client.get(f'/api/pigs/{pig_id}/lineage-tree')

        self.assertEqual(403, response.status_code)

    def test_normalize_and_name_lookup_are_case_insensitive(self):
        with self.app.app_context():
            user = User(username='Breeder', password_hash='x')
            db.session.add(user)
            db.session.flush()
            db.session.add(Pig(user_id=user.id, name='  Baron   Groin  ', sex='M'))
            db.session.commit()

            self.assertEqual('baron groin', normalize_pig_name(' Baron   Groin '))
            self.assertTrue(is_pig_name_taken('baron groin'))
            self.assertEqual('Baron Groin 2', build_unique_pig_name('Baron Groin'))

    def test_create_offspring_rejects_same_sex_parents(self):
        user = SimpleNamespace(id=1, username='Breeder', barn_heritage_bonus=0.0)
        pig_a = SimpleNamespace(id=1, sex='M')
        pig_b = SimpleNamespace(id=2, sex='M')

        with self.assertRaises(ValidationError):
            create_offspring(user, pig_a, pig_b)

    @patch('services.pig_lineage_service.get_pig_settings', return_value=SimpleNamespace(default_max_races=9))
    @patch('services.pig_lineage_service.generate_weight_kg_for_profile', return_value=118.5)
    @patch('services.pig_lineage_service.random.uniform', return_value=0.0)
    @patch('services.pig_lineage_service.random.choice', side_effect=lambda values: values[0])
    def test_create_offspring_builds_child_from_parent_profiles(
        self,
        _choice_mock,
        _uniform_mock,
        _weight_mock,
        _settings_mock,
    ):
        user = SimpleNamespace(id=3, username='Breeder', barn_heritage_bonus=2.0)
        parent_a = SimpleNamespace(
            id=10,
            sex='M',
            name='Atlas',
            lineage_name='Maison Atlas',
            rarity='rare',
            origin_country='France',
            origin_flag='FR',
            generation=2,
            lineage_boost=1.0,
            vitesse=20.0,
            endurance=16.0,
            agilite=14.0,
            force=18.0,
            intelligence=12.0,
            moral=11.0,
            gene_vitesse=52.0,
            gene_endurance=50.0,
            gene_agilite=48.0,
            gene_force=54.0,
            gene_intelligence=46.0,
            gene_moral=44.0,
        )
        parent_b = SimpleNamespace(
            id=11,
            sex='F',
            name='Bella',
            lineage_name='Maison Bella',
            rarity='rare',
            origin_country='France',
            origin_flag='FR',
            generation=3,
            lineage_boost=2.0,
            vitesse=14.0,
            endurance=18.0,
            agilite=16.0,
            force=15.0,
            intelligence=13.0,
            moral=17.0,
            gene_vitesse=50.0,
            gene_endurance=48.0,
            gene_agilite=52.0,
            gene_force=49.0,
            gene_intelligence=47.0,
            gene_moral=45.0,
        )

        with self.app.app_context():
            child = create_offspring(user, parent_a, parent_b, name='Porcelet Maison')

        self.assertEqual(user.id, child.user_id)
        self.assertEqual('Porcelet Maison', child.name)
        self.assertEqual('Maison Atlas', child.lineage_name)
        self.assertEqual(4, child.generation)
        self.assertEqual(10, child.sire_id)
        self.assertEqual(11, child.dam_id)
        self.assertEqual(9, child.max_races)
        self.assertEqual(118.5, child.weight_kg)
        self.assertGreater(child.force, 0)
        self.assertGreater(child.gene_force, 0)

    def test_get_pig_heritage_value_supports_dict_inputs(self):
        heritage_value = get_pig_heritage_value({
            'races_won': 4,
            'level': 3,
            'rarity': 'legendaire',
            'lineage_boost': 2.5,
        })

        self.assertGreater(heritage_value, 0)


if __name__ == '__main__':
    unittest.main()
