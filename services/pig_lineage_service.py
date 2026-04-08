from dataclasses import dataclass
import random

from sqlalchemy import text

from config.game_rules import PIG_DEFAULTS, PIG_HERITAGE_RULES, PIG_LIMITS, PIG_OFFSPRING_RULES
from content.pigs_catalog import PIG_EMOJIS, PIG_ORIGINS, PRELOADED_PIG_NAMES
from exceptions import ValidationError
from extensions import db
from models import Pig
from services.pig_power_service import generate_weight_kg_for_profile, get_pig_settings


@dataclass(frozen=True)
class PigHeritageSnapshot:
    races_won: int
    level: int
    rarity: str
    lineage_boost: float

    @classmethod
    def from_source(cls, pig):
        if isinstance(pig, dict):
            return cls(
                races_won=int(pig.get('races_won') or 0),
                level=max(1, int(pig.get('level') or 1)),
                rarity=str(pig.get('rarity') or 'commun'),
                lineage_boost=float(pig.get('lineage_boost') or 0.0),
            )
        return cls(
            races_won=int(getattr(pig, 'races_won', 0) or 0),
            level=max(1, int(getattr(pig, 'level', 1) or 1)),
            rarity=str(getattr(pig, 'rarity', 'commun') or 'commun'),
            lineage_boost=float(getattr(pig, 'lineage_boost', 0.0) or 0.0),
        )


def random_pig_sex():
    return random.choice(['M', 'F'])


def get_lineage_label(pig):
    return pig.lineage_name or pig.name


def get_pig_heritage_value(pig):
    heritage = PigHeritageSnapshot.from_source(pig)
    rarity_bonus = PIG_HERITAGE_RULES.rarity_bonus_by_key.get(heritage.rarity, 0.0)
    return round(
        (heritage.races_won * PIG_HERITAGE_RULES.heritage_races_won_factor)
        + max(0, heritage.level - 1) * PIG_HERITAGE_RULES.heritage_level_factor
        + heritage.lineage_boost
        + rarity_bonus,
        2,
    )


def _serialize_lineage_pig_node(pig, relation=None, depth=0):
    if not pig:
        return None
    return {
        'id': pig.id,
        'name': pig.name,
        'emoji': pig.emoji or '🐷',
        'sex': pig.sex or 'M',
        'generation': pig.generation or 1,
        'lineage_name': pig.lineage_name,
        'lineage_label': get_lineage_label(pig),
        'rarity': pig.rarity or 'commun',
        'level': pig.level or 1,
        'races_won': pig.races_won or 0,
        'lineage_boost': round(float(pig.lineage_boost or 0.0), 2),
        'is_alive': bool(pig.is_alive),
        'owner_name': pig.owner.username if getattr(pig, 'owner', None) else None,
        'relation': relation,
        'depth': depth,
    }


def _fetch_lineage_relations(root_pig_id, max_depth=4):
    query = text(
        """
        WITH RECURSIVE ancestor_links AS (
            SELECT
                p.id AS pig_id,
                p.sire_id AS sire_id,
                p.dam_id AS dam_id,
                CAST(NULL AS INTEGER) AS relative_id,
                CAST(NULL AS TEXT) AS relation,
                0 AS depth
            FROM pig AS p
            WHERE p.id = :pig_id
            UNION ALL
            SELECT
                parent.id AS pig_id,
                parent.sire_id AS sire_id,
                parent.dam_id AS dam_id,
                child.pig_id AS relative_id,
                CASE
                    WHEN child.sire_id = parent.id THEN 'sire'
                    WHEN child.dam_id = parent.id THEN 'dam'
                    ELSE NULL
                END AS relation,
                child.depth + 1 AS depth
            FROM pig AS parent
            JOIN ancestor_links AS child
                ON parent.id = child.sire_id OR parent.id = child.dam_id
            WHERE child.depth < :max_depth
        ),
        descendant_links AS (
            SELECT
                p.id AS pig_id,
                p.sire_id AS sire_id,
                p.dam_id AS dam_id,
                CAST(NULL AS INTEGER) AS relative_id,
                CAST(NULL AS TEXT) AS relation,
                0 AS depth
            FROM pig AS p
            WHERE p.id = :pig_id
            UNION ALL
            SELECT
                child.id AS pig_id,
                child.sire_id AS sire_id,
                child.dam_id AS dam_id,
                parent.pig_id AS relative_id,
                CASE
                    WHEN child.sire_id = parent.pig_id THEN 'child_sire'
                    WHEN child.dam_id = parent.pig_id THEN 'child_dam'
                    ELSE NULL
                END AS relation,
                parent.depth + 1 AS depth
            FROM pig AS child
            JOIN descendant_links AS parent
                ON child.sire_id = parent.pig_id OR child.dam_id = parent.pig_id
            WHERE parent.depth < :max_depth
        )
        SELECT pig_id, relative_id, relation, depth, 'ancestor' AS branch
        FROM ancestor_links
        UNION ALL
        SELECT pig_id, relative_id, relation, depth, 'descendant' AS branch
        FROM descendant_links
        """
    )
    rows = db.session.execute(query, {'pig_id': int(root_pig_id), 'max_depth': int(max_depth)}).mappings().all()
    return [dict(row) for row in rows]


def _build_ancestor_branch(root_pig_id, pigs_by_id, parent_map, depth_map):
    if root_pig_id not in pigs_by_id:
        return None
    root_node = _serialize_lineage_pig_node(pigs_by_id[root_pig_id], depth=0)
    root_node['parents'] = []
    for relation in ('sire', 'dam'):
        parent_id = parent_map.get(root_pig_id, {}).get(relation)
        if not parent_id or parent_id not in pigs_by_id:
            continue
        parent_node = _build_ancestor_branch(parent_id, pigs_by_id, parent_map, depth_map)
        if not parent_node:
            continue
        parent_node['relation'] = relation
        parent_node['depth'] = depth_map.get(parent_id, 1)
        root_node['parents'].append(parent_node)
    return root_node


def _build_descendant_branch(root_pig_id, pigs_by_id, child_map, depth_map):
    if root_pig_id not in pigs_by_id:
        return None
    root_node = _serialize_lineage_pig_node(pigs_by_id[root_pig_id], depth=0)
    root_node['children'] = []
    children = child_map.get(root_pig_id, [])
    children.sort(key=lambda item: (depth_map.get(item[0], 0), item[1], item[0]))
    for child_id, relation in children:
        if child_id not in pigs_by_id:
            continue
        child_node = _build_descendant_branch(child_id, pigs_by_id, child_map, depth_map)
        if not child_node:
            continue
        child_node['relation'] = relation
        child_node['depth'] = depth_map.get(child_id, 1)
        root_node['children'].append(child_node)
    return root_node


def build_pig_lineage_tree(pig_or_id, max_depth=4):
    pig_id = int(pig_or_id.id if isinstance(pig_or_id, Pig) else pig_or_id)
    relations = _fetch_lineage_relations(pig_id, max_depth=max_depth)
    if not relations:
        return None

    unique_ids = {row['pig_id'] for row in relations if row['pig_id']}
    pigs = (
        Pig.query
        .filter(Pig.id.in_(unique_ids))
        .all()
    )
    pigs_by_id = {pig.id: pig for pig in pigs}
    if pig_id not in pigs_by_id:
        return None

    parent_map = {}
    child_map = {}
    ancestor_depths = {pig_id: 0}
    descendant_depths = {pig_id: 0}

    for row in relations:
        current_id = row['pig_id']
        relative_id = row['relative_id']
        relation = row['relation']
        depth = int(row['depth'] or 0)
        branch = row['branch']

        if branch == 'ancestor':
            ancestor_depths[current_id] = min(depth, ancestor_depths.get(current_id, depth))
            if relative_id and relation in ('sire', 'dam'):
                parent_map.setdefault(relative_id, {})
                if relation not in parent_map[relative_id]:
                    parent_map[relative_id][relation] = current_id
        else:
            descendant_depths[current_id] = min(depth, descendant_depths.get(current_id, depth))
            if relative_id and relation in ('child_sire', 'child_dam'):
                existing_children = child_map.setdefault(relative_id, [])
                pair = (current_id, relation)
                if pair not in existing_children:
                    existing_children.append(pair)

    focus_node = _serialize_lineage_pig_node(pigs_by_id[pig_id], relation='focus', depth=0)
    focus_node['parents'] = []
    focus_node['children'] = []

    for relation in ('sire', 'dam'):
        parent_id = parent_map.get(pig_id, {}).get(relation)
        if parent_id:
            branch = _build_ancestor_branch(parent_id, pigs_by_id, parent_map, ancestor_depths)
            if branch:
                branch['relation'] = relation
                branch['depth'] = ancestor_depths.get(parent_id, 1)
                focus_node['parents'].append(branch)

    children = child_map.get(pig_id, [])
    children.sort(key=lambda item: (descendant_depths.get(item[0], 0), item[1], item[0]))
    for child_id, relation in children:
        branch = _build_descendant_branch(child_id, pigs_by_id, child_map, descendant_depths)
        if branch:
            branch['relation'] = relation
            branch['depth'] = descendant_depths.get(child_id, 1)
            focus_node['children'].append(branch)

    return {
        'focus': focus_node,
        'meta': {
            'pig_id': pig_id,
            'max_depth': max_depth,
            'ancestor_count': max(0, len(ancestor_depths) - 1),
            'descendant_count': max(0, len(descendant_depths) - 1),
            'node_count': len(unique_ids),
        },
    }


def normalize_pig_name(name):
    return ' '.join((name or '').split()).casefold()


def is_pig_name_taken(name, exclude_pig_id=None):
    normalized = normalize_pig_name(name)
    if not normalized:
        return False
    pigs = Pig.query
    if exclude_pig_id is not None:
        pigs = pigs.filter(Pig.id != exclude_pig_id)
    return any(normalize_pig_name(pig.name) == normalized for pig in pigs.all())


def build_unique_pig_name(base_name, fallback_prefix='Cochon'):
    candidate = ' '.join((base_name or '').split())[:80]
    if not candidate:
        candidate = fallback_prefix
    if not is_pig_name_taken(candidate):
        return candidate
    suffix = 2
    while True:
        suffix_label = f' {suffix}'
        trimmed = candidate[:max(1, 80 - len(suffix_label))].rstrip()
        unique_name = f'{trimmed}{suffix_label}'
        if not is_pig_name_taken(unique_name):
            return unique_name
        suffix += 1


_GENE_KEYS = ['gene_vitesse', 'gene_endurance', 'gene_agilite', 'gene_force', 'gene_intelligence', 'gene_moral']
_GENE_STAT_MAP = {
    'gene_vitesse': 'vitesse',
    'gene_endurance': 'endurance',
    'gene_agilite': 'agilite',
    'gene_force': 'force',
    'gene_intelligence': 'intelligence',
    'gene_moral': 'moral',
}


def init_pig_genes_random(pig, low=35.0, high=65.0):
    """Initialise les 6 gènes d'un cochon de première génération avec des valeurs aléatoires."""
    for gene_key in _GENE_KEYS:
        setattr(pig, gene_key, round(random.uniform(low, high), 1))


def apply_origin_bonus(pig, origin):
    base_value = getattr(pig, origin['bonus_stat']) or PIG_DEFAULTS.stat
    setattr(pig, origin['bonus_stat'], base_value + origin['bonus'])


def create_offspring(user, parent_a, parent_b, name=None):
    if parent_a.sex == parent_b.sex:
        raise ValidationError("La reproduction nécessite un mâle et une femelle !")

    sire = parent_a if parent_a.sex == 'M' else parent_b
    dam = parent_a if parent_a.sex == 'F' else parent_b
    lineage_name = parent_a.lineage_name or parent_b.lineage_name or f"Maison {user.username}"
    barn_bonus = user.barn_heritage_bonus or 0.0
    child = Pig(
        user_id=user.id,
        name=build_unique_pig_name(name or f"Porcelet {lineage_name}", fallback_prefix='Porcelet'),
        emoji=random.choice(PIG_EMOJIS),
        sex=random_pig_sex(),
        rarity=parent_a.rarity if parent_a.rarity == parent_b.rarity else random.choice([parent_a.rarity, parent_b.rarity, 'commun']),
        origin_country=random.choice([parent_a.origin_country, parent_b.origin_country]),
        origin_flag=random.choice([parent_a.origin_flag, parent_b.origin_flag]),
        lineage_name=lineage_name,
        generation=max(parent_a.generation or 1, parent_b.generation or 1) + 1,
        sire_id=sire.id,
        dam_id=dam.id,
        max_races=get_pig_settings().default_max_races,
        lineage_boost=round(
            ((parent_a.lineage_boost or 0.0) + (parent_b.lineage_boost or 0.0)) * PIG_OFFSPRING_RULES.parent_lineage_factor
            + (barn_bonus * PIG_OFFSPRING_RULES.barn_bonus_factor),
            2,
        ),
    )
    for stat in ['vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral']:
        base = (getattr(parent_a, stat, PIG_DEFAULTS.stat) + getattr(parent_b, stat, PIG_DEFAULTS.stat)) / 2
        inherited = (
            base * PIG_OFFSPRING_RULES.inherited_stats_parent_average_factor
            + random.uniform(
                PIG_OFFSPRING_RULES.inherited_stats_random_min,
                PIG_OFFSPRING_RULES.inherited_stats_random_max,
            )
            + child.lineage_boost
        )
        setattr(
            child,
            stat,
            round(min(PIG_LIMITS.max_value, max(PIG_OFFSPRING_RULES.inherited_stat_floor, inherited)), 1),
        )
    # Héritage des gènes — potentiel génétique
    for gene_key, stat_key in _GENE_STAT_MAP.items():
        val_a = getattr(parent_a, gene_key, None) or getattr(parent_a, stat_key, PIG_DEFAULTS.stat)
        val_b = getattr(parent_b, gene_key, None) or getattr(parent_b, stat_key, PIG_DEFAULTS.stat)
        inherited_gene = (val_a + val_b) / 2 + random.uniform(-8, 8)
        setattr(child, gene_key, round(max(5.0, min(100.0, inherited_gene)), 1))

    child.energy = PIG_OFFSPRING_RULES.initial_energy
    child.hunger = PIG_OFFSPRING_RULES.initial_hunger
    child.happiness = min(
        PIG_LIMITS.max_value,
        round(
            PIG_OFFSPRING_RULES.initial_happiness_base
            + (barn_bonus * PIG_OFFSPRING_RULES.initial_happiness_barn_bonus_factor),
            1,
        ),
    )
    child.weight_kg = generate_weight_kg_for_profile(child, level=child.level)
    return child


def create_offspring_from_stud(user, stud, name=None):
    """Crée un porcelet depuis un géniteur du Haras Porcin (sans 2e parent requis).
    Le géniteur contribue 60 % de ses stats/gènes ; un parent fantôme à niveau de base complète."""
    _PHANTOM_STAT = 12.0
    _PHANTOM_GENE = 45.0
    barn_bonus = user.barn_heritage_bonus or 0.0
    lineage_name = stud.lineage_name or f"Lignée {stud.name}"

    child = Pig(
        user_id=user.id,
        name=build_unique_pig_name(
            name or f"Porcelet de {stud.name}",
            fallback_prefix='Porcelet',
        ),
        emoji=random.choice(PIG_EMOJIS),
        sex=random_pig_sex(),
        rarity=stud.rarity if random.random() < 0.40 else 'commun',
        origin_country=stud.origin_country,
        origin_flag=stud.origin_flag,
        lineage_name=lineage_name,
        generation=(stud.generation or 1) + 1,
        sire_id=stud.id if stud.sex == 'M' else None,
        dam_id=stud.id if stud.sex == 'F' else None,
        max_races=get_pig_settings().default_max_races,
        lineage_boost=round(
            (stud.lineage_boost or 0.0) * 0.50
            + barn_bonus * PIG_OFFSPRING_RULES.barn_bonus_factor,
            2,
        ),
    )

    # Stats héritées : 60 % stud + 40 % fantôme
    for stat in ['vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral']:
        stud_stat = getattr(stud, stat, PIG_DEFAULTS.stat) or PIG_DEFAULTS.stat
        base = stud_stat * 0.60 + _PHANTOM_STAT * 0.40
        inherited = (
            base * PIG_OFFSPRING_RULES.inherited_stats_parent_average_factor
            + random.uniform(
                PIG_OFFSPRING_RULES.inherited_stats_random_min,
                PIG_OFFSPRING_RULES.inherited_stats_random_max,
            )
            + child.lineage_boost
        )
        setattr(
            child,
            stat,
            round(min(PIG_LIMITS.max_value, max(PIG_OFFSPRING_RULES.inherited_stat_floor, inherited)), 1),
        )

    # Gènes hérités : 60 % stud + 40 % fantôme (meilleure transmissibilité que la reproduction normale)
    for gene_key in _GENE_KEYS:
        stud_gene = getattr(stud, gene_key, None) or _PHANTOM_GENE
        inherited_gene = stud_gene * 0.60 + _PHANTOM_GENE * 0.40 + random.uniform(-6, 6)
        setattr(child, gene_key, round(max(5.0, min(100.0, inherited_gene)), 1))

    child.energy = PIG_OFFSPRING_RULES.initial_energy
    child.hunger = PIG_OFFSPRING_RULES.initial_hunger
    child.happiness = min(
        PIG_LIMITS.max_value,
        round(
            PIG_OFFSPRING_RULES.initial_happiness_base
            + barn_bonus * PIG_OFFSPRING_RULES.initial_happiness_barn_bonus_factor,
            1,
        ),
    )
    child.weight_kg = generate_weight_kg_for_profile(child, level=child.level)
    return child


def create_preloaded_admin_pigs(admin_user):
    if not admin_user:
        return 0
    created = 0
    for index, pig_name in enumerate(PRELOADED_PIG_NAMES):
        if is_pig_name_taken(pig_name):
            continue
        origin = PIG_ORIGINS[index % len(PIG_ORIGINS)]
        pig = Pig(
            user_id=admin_user.id,
            name=pig_name,
            emoji=PIG_EMOJIS[index % len(PIG_EMOJIS)],
            sex=random_pig_sex(),
            origin_country=origin['country'],
            origin_flag=origin['flag'],
            lineage_name='Maison Admin',
            max_races=get_pig_settings().default_max_races,
        )
        apply_origin_bonus(pig, origin)
        pig.weight_kg = generate_weight_kg_for_profile(pig)
        db.session.add(pig)
        created += 1
    return created
