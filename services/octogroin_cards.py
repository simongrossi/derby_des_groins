"""Octogroin — atout & contre cards catalogue.

Each card has:
- `id`: short stable string used in DB / API payloads.
- `label`, `emoji`, `description`: for the UI.
- `kind`: 'atout' (offensive/utility) or 'contre' (defensive/reactive).
- `scope`: 'slot' (effect lives on the specific pair only) or 'round' (effect
  spans the whole round once played) or 'instant' (fires once at play time).

The effect logic itself lives in `services/octogroin_engine.py` inside
`_resolve_pair` and the round orchestration loop — this module is pure
metadata so the front, the admin and the tests can all agree on the list.
"""

from __future__ import annotations

import random

CARD_POOL_SIZE = 10
HAND_SIZE = 3
MAX_CARDS_PER_ROUND = 1


CARDS = {
    # ── ATOUTS ───────────────────────────────────────────────────────────
    'berserk': {
        'id': 'berserk',
        'label': 'Berserk',
        'emoji': '🔥',
        'kind': 'atout',
        'scope': 'slot',
        'description': "Ta Charge sur ce slot pousse ×2 (force doublée). Coûte -20 endurance comme une Charge normale.",
    },
    'second_souffle': {
        'id': 'second_souffle',
        'label': 'Second souffle',
        'emoji': '💪',
        'kind': 'atout',
        'scope': 'instant',
        'description': "Restaure immédiatement +40 endurance (pas de combat ce slot).",
    },
    'feinte': {
        'id': 'feinte',
        'label': 'Feinte parfaite',
        'emoji': '🎯',
        'kind': 'atout',
        'scope': 'slot',
        'description': "Ton Esquive sur ce slot réussit à 100% (coût -15 endurance).",
    },
    'coup_bas': {
        'id': 'coup_bas',
        'label': 'Coup bas',
        'emoji': '🤥',
        'kind': 'atout',
        'scope': 'slot',
        'description': "Ton Charge traverse un Ancrage sans splat (coût -20 endurance).",
    },
    'taurus': {
        'id': 'taurus',
        'label': 'Taurus',
        'emoji': '🐂',
        'kind': 'atout',
        'scope': 'slot',
        'description': "Ton Ancrage sur ce slot inflige -50 endurance à l'attaquant (au lieu de -30).",
    },
    'grognement': {
        'id': 'grognement',
        'label': 'Grognement',
        'emoji': '🐷',
        'kind': 'atout',
        'scope': 'instant',
        'description': "Draine immédiatement -25 endurance chez l'adversaire (pas de combat ce slot).",
    },
    # ── CONTRES ──────────────────────────────────────────────────────────
    'contre_atout': {
        'id': 'contre_atout',
        'label': 'Contre-atout',
        'emoji': '❌',
        'kind': 'contre',
        'scope': 'round',
        'description': "Annule le premier atout adverse joué pendant cette manche (peu importe le slot).",
    },
    'patine': {
        'id': 'patine',
        'label': 'Patine',
        'emoji': '🧊',
        'kind': 'contre',
        'scope': 'round',
        'description': "Tu es immune à toute poussée pendant cette manche.",
    },
    'vol_energie': {
        'id': 'vol_energie',
        'label': "Vol d'énergie",
        'emoji': '⚡',
        'kind': 'contre',
        'scope': 'round',
        'description': "Tu récupères 50% de l'endurance dépensée par l'adversaire pendant cette manche.",
    },
    'miroir': {
        'id': 'miroir',
        'label': 'Miroir',
        'emoji': '🪞',
        'kind': 'contre',
        'scope': 'round',
        'description': "50% des poussées reçues pendant cette manche sont renvoyées à l'adversaire.",
    },
}


def all_card_ids() -> list[str]:
    return list(CARDS.keys())


def is_valid_card(card_id) -> bool:
    return card_id in CARDS


def get_card(card_id) -> dict | None:
    return CARDS.get(card_id)


def get_kind(card_id) -> str | None:
    c = CARDS.get(card_id)
    return c['kind'] if c else None


def draw_hand(seed: int, size: int = HAND_SIZE) -> list[str]:
    """Deterministic draw of `size` cards from the full pool, for one player.
    Two players sharing the same `seed` would get the same hand — callers are
    expected to seed per (duel_id, player_slot) to give distinct hands."""
    rng = random.Random(seed)
    pool = list(CARDS.keys())
    rng.shuffle(pool)
    return pool[:size]
