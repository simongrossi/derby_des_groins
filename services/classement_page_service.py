from models import User
from services.classement_queries import load_classement_query_data
from services.classement_ranking_builder import (
    build_chart_data,
    build_empty_classement_context,
    build_rankings,
)
from services.trophy_builder_service import build_awards


def build_empty_classement_page_context():
    return build_empty_classement_context()


def build_classement_page_context():
    users = User.query.all()
    if not users:
        return build_empty_classement_page_context()

    query_data = load_classement_query_data()
    rankings = build_rankings(users, query_data)
    return {
        'rankings': rankings,
        'chart_data': build_chart_data(rankings),
        'awards': build_awards(rankings),
    }
