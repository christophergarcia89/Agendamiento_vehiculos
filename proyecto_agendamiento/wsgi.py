import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto_agendamiento.settings') # <-- ¡Importante!

application = get_wsgi_application()