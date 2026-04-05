"""Static UI metadata for stats and scheduling labels."""

STAT_LABELS = {
    'vitesse': 'VIT',
    'endurance': 'END',
    'agilite': 'AGI',
    'force': 'FOR',
    'intelligence': 'INT',
    'moral': 'MOR',
}

STAT_DESCRIPTIONS = {
    'vitesse': 'Vitesse de pointe sur terrain plat. Crucial pour le sprint final.',
    'endurance': 'Résistance à la fatigue. Permet de maintenir une vitesse élevée plus longtemps.',
    'agilite': 'Aisance dans les virages et les dépassements. Réduit les risques de bousculade.',
    'force': 'Puissance de poussée. Utile pour les départs et les terrains difficiles.',
    'intelligence': "Lecture de course. Améliore les trajectoires et la gestion de l'effort.",
    'moral': 'Détermination du cochon. Un moral haut donne un bonus global à toutes les stats en course.',
}

JOURS_FR = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

PIG_COURSE_SEGMENT_TYPES = ['PLAT', 'MONTEE', 'DESCENTE', 'VIRAGE', 'BOUE']
