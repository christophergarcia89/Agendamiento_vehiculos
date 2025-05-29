from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import UsuarioSistema

@receiver(post_save, sender=User)
def crear_perfil_usuario_sistema(sender, instance, created, **kwargs):
    if created:
        UsuarioSistema.objects.create(
            user=instance,
            nombre_usuario_completo=instance.get_full_name() or instance.username,
            razon_social_empresa='',
            rut_empresa='',
            ciudad=''
        )