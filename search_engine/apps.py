from django.apps import AppConfig


class SearchEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'search_engine'

    def ready(self):
        """Import signals when app is ready"""
        import search_engine.signals  # noqa
