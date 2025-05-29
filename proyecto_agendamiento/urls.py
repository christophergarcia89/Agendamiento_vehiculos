# proyecto_principal/urls.py (o como se llame tu directorio de proyecto)
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('agendamiento/', include('agendamiento.urls', namespace='agendamiento')),
    
    # Redirección de la raíz del sitio a la página de login o selección de fecha de agendamiento
    path('', lambda request: redirect('agendamiento:login', permanent=False), name='raiz_sitio'), 
    # O si prefieres que vaya directo a seleccionar fecha si ya está logueado:
    # path('', lambda request: redirect('agendamiento:seleccionar_fecha' if request.user.is_authenticated else 'agendamiento:login', permanent=False), name='raiz_sitio'),
]