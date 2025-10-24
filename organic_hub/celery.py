import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'organic_hub.settings')

app = Celery('organic_hub')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
