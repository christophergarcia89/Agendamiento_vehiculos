from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm # Para login y registro
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.http import Http404, HttpResponseForbidden, HttpResponse # Asegúrate de importar HttpResponse si lo usas directamente
from django.urls import reverse # Importante para el redirect con namespace
from .models import Vehiculo, UsuarioSistema, Reserva
from .forms import FechaSeleccionForm, ReservaForm
from datetime import date, time, timedelta, datetime
from django.core.exceptions import ValidationError # Importar ValidationError


# Horarios de operación (ej: 8 AM a 6 PM, último bloque empieza a las 5 PM)
HORARIOS_OPERACION = [time(h) for h in range(8, 18)] 

@login_required
def seleccionar_fecha_view(request):
    """
    Vista para que el usuario seleccione una fecha para ver la disponibilidad.
    """
    if not hasattr(request.user, 'perfil_sistema'):
        messages.error(request, "Su cuenta de usuario no está completamente configurada para el sistema de agendamiento. Por favor, contacte al administrador.")
        return redirect('agendamiento:pagina_inicio_o_perfil') # Redirigir a una página apropiada
    
    perfil_usuario = request.user.perfil_sistema
    
    if request.method == 'POST':
        form = FechaSeleccionForm(request.POST)
        if form.is_valid():
            fecha_seleccionada = form.cleaned_data['fecha']
            # Redirigir a la vista de disponibilidad para esa fecha
            return redirect('agendamiento:mostrar_disponibilidad', fecha_str=fecha_seleccionada.isoformat())
    else:
        form = FechaSeleccionForm()

    context = {
        'form': form,
        'perfil_usuario': perfil_usuario,
        'titulo_pagina': "Seleccionar Fecha para Agendamiento"
    }
    return render(request, 'agendamiento/seleccionar_fecha.html', context)

@login_required
def mostrar_disponibilidad_view(request, fecha_str):
    """
    Muestra la disponibilidad de vehículos para la razón social del usuario
    en la fecha seleccionada.
    """
    try:
        fecha_seleccionada = date.fromisoformat(fecha_str)
    except ValueError:
        raise Http404("Formato de fecha inválido.")

    if not hasattr(request.user, 'perfil_sistema'):
        messages.error(request, "Perfil de sistema no encontrado para el usuario.")
        return redirect('agendamiento:seleccionar_fecha') # O alguna otra página de error/inicio

    perfil_usuario = request.user.perfil_sistema
    razon_social_usuario = perfil_usuario.razon_social_empresa

    # Filtrar vehículos por la razón social del usuario
    vehiculos_empresa = Vehiculo.objects.filter(razon_social=razon_social_usuario, estado='Activo').order_by('marca', 'modelo')
    if not vehiculos_empresa.exists():
        messages.info(request, f"No hay vehículos activos registrados para la empresa '{razon_social_usuario}'.")
    
    # Obtener todas las reservas para la fecha seleccionada y los vehículos de la empresa
    reservas_del_dia = Reserva.objects.filter(
        vehiculo__in=vehiculos_empresa,
        fecha_reserva=fecha_seleccionada
    ).select_related('vehiculo') # Optimización

    disponibilidad_data = {}

    for vehiculo in vehiculos_empresa:
        horarios_vehiculo = {}
        reservas_vehiculo_dia = reservas_del_dia.filter(vehiculo=vehiculo)
        
        horas_reservadas_vehiculo = {r.hora_inicio_reserva: r for r in reservas_vehiculo_dia}

        for hora_inicio_bloque in HORARIOS_OPERACION:
            hora_fin_bloque = (datetime.combine(date.today(), hora_inicio_bloque) + timedelta(hours=1)).time()
            texto_display_hora = f"{hora_inicio_bloque.strftime('%H:%M')} - {hora_fin_bloque.strftime('%H:%M')}"
            
            reserva_actual = horas_reservadas_vehiculo.get(hora_inicio_bloque)
            
            if reserva_actual:
                disponible = False
                reservado_por_mi = (reserva_actual.usuario == perfil_usuario)
                texto_reserva = "Reservado por ti" if reservado_por_mi else "Reservado"
            else:
                disponible = True
                reservado_por_mi = False
                texto_reserva = "Disponible"

            horarios_vehiculo[hora_inicio_bloque.strftime('%H:%M:%S')] = {
                'display': texto_display_hora,
                'disponible': disponible,
                'reservado_por_mi': reservado_por_mi,
                'texto_reserva': texto_reserva,
                'hora_inicio_obj': hora_inicio_bloque # para el form
            }
        
        disponibilidad_data[vehiculo.id] = {
            'vehiculo': vehiculo,
            'horarios': horarios_vehiculo
        }
    
    context = {
        'fecha_seleccionada': fecha_seleccionada,
        'disponibilidad_data': disponibilidad_data,
        'perfil_usuario': perfil_usuario,
        'titulo_pagina': f"Disponibilidad para el {fecha_seleccionada.strftime('%d/%m/%Y')}",
        'horarios_operacion_display': [(h.strftime('%H:%M:%S'), f"{h.strftime('%H:%M')} - {(datetime.combine(date.today(), h) + timedelta(hours=1)).time().strftime('%H:%M')}") for h in HORARIOS_OPERACION]
    }
    return render(request, 'agendamiento/mostrar_disponibilidad.html', context)


@login_required
@transaction.atomic # Asegura que todas las reservas se creen o ninguna
def reservar_vehiculo_view(request, vehiculo_id, fecha_str):
    """
    Permite a un usuario seleccionar bloques horarios y crear reservas para un vehículo y fecha específicos.
    """
    try:
        fecha_seleccionada = date.fromisoformat(fecha_str)
    except ValueError:
        raise Http404("Formato de fecha inválido.")

    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)
    
    if not hasattr(request.user, 'perfil_sistema'):
        messages.error(request, "Perfil de sistema no encontrado.")
        return redirect('agendamiento:seleccionar_fecha')

    perfil_usuario = request.user.perfil_sistema

    if vehiculo.razon_social != perfil_usuario.razon_social_empresa:
        messages.error(request, "No tiene permiso para reservar este vehículo, no pertenece a su empresa.")
        return redirect('agendamiento:mostrar_disponibilidad', fecha_str=fecha_seleccionada.isoformat())


    if fecha_seleccionada < timezone.now().date():
        messages.error(request, "No puede realizar reservas para fechas pasadas.")
        return redirect('agendamiento:mostrar_disponibilidad', fecha_str=fecha_seleccionada.isoformat())

    if request.method == 'POST':
        form = ReservaForm(request.POST, vehiculo=vehiculo, fecha=fecha_seleccionada, usuario_sistema=perfil_usuario)
        if form.is_valid():
            try:
                reservas_creadas = form.save() 
                if reservas_creadas:
                    nombres_bloques = [f"{r.hora_inicio_reserva.strftime('%H:%M')}-{r.hora_fin_reserva.strftime('%H:%M')}" for r in reservas_creadas]
                    messages.success(request, 
                                     f"Reserva(s) para {vehiculo.patente} el {fecha_seleccionada.strftime('%d/%m/%Y')} "
                                     f"en los bloques: {', '.join(nombres_bloques)} realizada(s) con éxito.")
                    return redirect('agendamiento:mostrar_disponibilidad', fecha_str=fecha_seleccionada.isoformat())
                else:
                    messages.error(request, "No se pudieron crear las reservas. Verifique los errores.")
            except ValidationError as e: 
                messages.error(request, f"Error al crear la reserva: {e}")
            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado: {e}")
    else:
        form = ReservaForm(vehiculo=vehiculo, fecha=fecha_seleccionada, usuario_sistema=perfil_usuario)

    reservas_existentes_vehiculo = Reserva.objects.filter(
        vehiculo=vehiculo,
        fecha_reserva=fecha_seleccionada
    ).values_list('hora_inicio_reserva', flat=True)
    
    horarios_disponibles_info = []
    for hora_inicio_op in HORARIOS_OPERACION:
        hora_fin_op = (datetime.combine(date.today(), hora_inicio_op) + timedelta(hours=1)).time()
        esta_reservado = hora_inicio_op in reservas_existentes_vehiculo
        horarios_disponibles_info.append({
            'hora_inicio': hora_inicio_op,
            'hora_fin': hora_fin_op,
            'display': f"{hora_inicio_op.strftime('%H:%M')} - {hora_fin_op.strftime('%H:%M')}",
            'id_checkbox': f"id_bloque_{hora_inicio_op.strftime('%H%M%S')}",
            'valor_checkbox': hora_inicio_op.strftime('%H:%M:%S'),
            'deshabilitado': esta_reservado,
            'texto_estado': "Reservado" if esta_reservado else "Disponible"
        })

    context = {
        'form': form,
        'vehiculo': vehiculo,
        'fecha_seleccionada': fecha_seleccionada,
        'perfil_usuario': perfil_usuario,
        'titulo_pagina': f"Reservar {vehiculo.patente} para el {fecha_seleccionada.strftime('%d/%m/%Y')}",
        'horarios_info': horarios_disponibles_info
    }
    return render(request, 'agendamiento/reservar_vehiculo.html', context)

def registro_usuario_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Registro exitoso. Ahora puedes iniciar sesión.")
            messages.info(request, "Un administrador debe completar la configuración de su perfil de empresa antes de poder agendar.")
            return redirect('agendamiento:login')
    else:
        form = UserCreationForm()
    return render(request, 'agendamiento/registro.html', {'form': form, 'titulo_pagina': "Registro de Usuario"})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, f"Bienvenido, {user.username}!")
            
            if hasattr(user, 'perfil_sistema'):
                 return redirect('agendamiento:seleccionar_fecha') 
            else:
                messages.warning(request, "Su perfil de empresa no está configurado. Contacte al administrador.")
                return redirect('agendamiento:seleccionar_fecha') 
    else:
        form = AuthenticationForm()
    return render(request, 'agendamiento/login.html', {'form': form, 'titulo_pagina': "Iniciar Sesión"})

@login_required
def logout_view(request):
    auth_logout(request)
    messages.info(request, "Has cerrado sesión.")
    return redirect('agendamiento:login')

def pagina_inicio_o_perfil(request):
    return render(request, 'agendamiento/base.html', {'titulo_pagina': 'Inicio', 'mensaje_generico': 'Bienvenido al sistema.'})