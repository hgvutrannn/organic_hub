from django.apps import AppConfig


class RecommendationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recommendations'
    
    def ready(self):
        """Register signals when app is ready"""
        import recommendations.signals  # noqa