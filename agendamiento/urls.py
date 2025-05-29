# agendamiento/urls.py
from django.urls import path
from . import views

app_name = 'agendamiento' # Namespace para las URLs de esta app

#urlpatterns = [
#    # Autenticación
#    path('registro/', views.registro_usuario_view, name='registro'),
#    path('login/', views.login_view, name='login'),
#    path('logout/', views.logout_view, name='logout'),
#
#    # Flujo de agendamiento
#    path('seleccionar-fecha/', views.seleccionar_fecha_view, name='seleccionar_fecha'),
#    path('disponibilidad/<str:fecha_str>/', views.mostrar_disponibilidad_view, name='mostrar_disponibilidad'),
#    path('reservar/<int:vehiculo_id>/<str:fecha_str>/', views.reservar_vehiculo_view, name='reservar_vehiculo'),
#    
#    # Placeholder para página de inicio o perfil (si es necesario)
#    path('inicio/', views.pagina_inicio_o_perfil, name='pagina_inicio_o_perfil'),
#    
#    # Podrías tener una URL raíz para la app si es necesario, ej:
#    # path('', views.seleccionar_fecha_view, name='index_agendamiento'), # O alguna otra vista por defecto
#]

urlpatterns = [
    # ... otras URLs de tu aplicación agendamiento ...

    # URL para la vista pagina_inicio_o_perfil
    path('inicio-perfil/', views.pagina_inicio_o_perfil, name='pagina_inicio_o_perfil'),

    # Ejemplo de cómo podría estar definida tu URL de login (ya debería existir)
    path('login/', views.login_view, name='login'),
    # Ejemplo de cómo podría estar definida tu URL de seleccionar_fecha (ya debería existir)
    path('seleccionar-fecha/', views.seleccionar_fecha_view, name='seleccionar_fecha'),
    path('mostrar-disponibilidad/<str:fecha_str>/', views.mostrar_disponibilidad_view, name='mostrar_disponibilidad'),
    path('reservar/<int:vehiculo_id>/<str:fecha_str>/', views.reservar_vehiculo_view, name='reservar_vehiculo'),
    path('registro/', views.registro_usuario_view, name='registro'),
    path('logout/', views.logout_view, name='logout'),
]