class Migrate:
    """Fallback léger pour environnements sans package Flask-Migrate."""

    def __init__(self, *args, **kwargs):
        self.app = None
        self.db = None

    def init_app(self, app, db=None, **kwargs):
        self.app = app
        self.db = db
