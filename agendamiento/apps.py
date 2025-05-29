from django.apps import AppConfig

class AgendamientoConfig(AppConfig):
    name = 'agendamiento'

    def ready(self):
        import agendamiento.signals