from helpers import get_config, set_config


def save_truffes_settings(form_data):
    daily_limit = form_data.get('truffe_daily_limit', '1')
    replay_cost = form_data.get('truffe_replay_cost', '2')
    set_config('truffe_daily_limit', daily_limit)
    set_config('truffe_replay_cost', replay_cost)
    return "Configuration des truffes sauvegardee !"


def build_admin_truffes_context():
    return {
        'daily_limit': get_config('truffe_daily_limit', '1'),
        'replay_cost': get_config('truffe_replay_cost', '2'),
    }
