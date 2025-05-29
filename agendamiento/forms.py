from django import forms
from .models import Reserva, Vehiculo
from django.utils import timezone
from datetime import time, date, timedelta, datetime
from django.core.exceptions import ValidationError
from django.utils import timezone

class ReservaForm(forms.Form):
    """
    Formulario para que los usuarios seleccionen los bloques horarios para una reserva.
    Este formulario se generará dinámicamente en la vista.
    Aquí definimos campos que podrían ser útiles para la validación o estructura.
    """
    vehiculo_id = forms.IntegerField(widget=forms.HiddenInput())
    fecha_reserva = forms.DateField(widget=forms.HiddenInput())
    # Los bloques horarios se añadirán dinámicamente como MultipleChoiceField o CheckboxSelectMultiple
    # Ejemplo: bloques_horarios = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=[...])

    def __init__(self, *args, **kwargs):
        self.vehiculo = kwargs.pop('vehiculo', None)
        self.fecha = kwargs.pop('fecha', None)
        self.usuario_sistema = kwargs.pop('usuario_sistema', None)
        super().__init__(*args, **kwargs)

        if self.vehiculo and self.fecha:
            self.fields['vehiculo_id'].initial = self.vehiculo.id
            self.fields['fecha_reserva'].initial = self.fecha
            
            # Generar choices para los bloques horarios disponibles
            # Horarios de operación: 08:00 a 18:00 (configurable)
            HORARIOS_OPERACION = [time(h) for h in range(8, 18)] # 8 AM a 5 PM (último bloque empieza a las 17:00)
            
            bloques_disponibles_choices = []
            reservas_existentes = Reserva.objects.filter(
                vehiculo=self.vehiculo,
                fecha_reserva=self.fecha
            ).values_list('hora_inicio_reserva', flat=True)

            for hora_inicio in HORARIOS_OPERACION:
                hora_fin = (datetime.combine(date.today(), hora_inicio) + timedelta(hours=1)).time()
                label = f"{hora_inicio.strftime('%H:%M')} - {hora_fin.strftime('%H:%M')}"
                if hora_inicio in reservas_existentes:
                    # Opción para deshabilitar o marcar como no disponible
                    # Por ahora, simplemente no lo añadimos como elegible si ya está reservado
                    # O se podría añadir pero deshabilitado en el widget (requiere JS o un widget custom)
                    pass # No añadir si ya está reservado por CUALQUIER usuario
                else:
                    bloques_disponibles_choices.append((hora_inicio.strftime('%H:%M:%S'), label))
            
            if bloques_disponibles_choices:
                self.fields['bloques_seleccionados'] = forms.MultipleChoiceField(
                    choices=bloques_disponibles_choices,
                    widget=forms.CheckboxSelectMultiple,
                    label="Seleccione los bloques horarios",
                    required=True
                )
            else:
                # Si no hay bloques, podríamos no mostrar el campo o mostrar un mensaje.
                # Por ahora, si no hay choices, el campo no se renderizará bien o dará error.
                # Mejor manejar esto en la vista/template.
                pass


    def clean_bloques_seleccionados(self):
        bloques = self.cleaned_data.get('bloques_seleccionados')
        if not bloques:
            raise forms.ValidationError("Debe seleccionar al menos un bloque horario.")
        
        # Validar que los bloques sean consecutivos si se seleccionan múltiples
        # (Esta validación puede ser compleja y a veces se prefiere permitir selección no contigua
        # y que el usuario sea responsable. Para este caso, no se implementará la validación de contigüidad estricta aquí)
        
        # Convertir strings de tiempo a objetos time
        try:
            horas_seleccionadas = sorted([time.fromisoformat(b) for b in bloques])
        except ValueError:
            raise forms.ValidationError("Formato de hora inválido en los bloques seleccionados.")

        # Validar nuevamente contra la base de datos en el momento de la sumisión (race condition)
        if self.vehiculo and self.fecha:
            for hora_inicio_str in bloques:
                hora_inicio = time.fromisoformat(hora_inicio_str)
                if Reserva.objects.filter(
                    vehiculo=self.vehiculo,
                    fecha_reserva=self.fecha,
                    hora_inicio_reserva=hora_inicio
                ).exists():
                    raise forms.ValidationError(
                        f"El bloque {hora_inicio.strftime('%H:%M')} para el vehículo {self.vehiculo.patente} "
                        f"fue reservado mientras realizaba su selección. Por favor, intente de nuevo."
                    )
        return horas_seleccionadas # Devolver objetos time

    def save(self):
        if not self.is_valid():
            return [] # No guardar si el formulario no es válido

        vehiculo_id = self.cleaned_data['vehiculo_id']
        fecha_reserva = self.cleaned_data['fecha_reserva']
        horas_inicio_seleccionadas = self.cleaned_data['bloques_seleccionados'] # Ya son objetos time

        vehiculo_obj = Vehiculo.objects.get(id=vehiculo_id)
        
        reservas_creadas = []
        for hora_inicio in horas_inicio_seleccionadas:
            # Calcular hora_fin
            hora_fin = (datetime.combine(date.today(), hora_inicio) + timedelta(hours=1)).time()
            
            reserva = Reserva(
                vehiculo=vehiculo_obj,
                usuario=self.usuario_sistema, # Asignado en la vista
                fecha_reserva=fecha_reserva,
                hora_inicio_reserva=hora_inicio,
                hora_fin_reserva=hora_fin # Se recalculará en el save() del modelo, pero es bueno tenerlo
            )
            try:
                reserva.save() # El save del modelo incluye full_clean()
                reservas_creadas.append(reserva)
            except ValidationError as e:
                # Si hay un error de validación (ej. duplicado por race condition)
                # Se podría agregar al form.errors o manejarlo.
                # Por ahora, si una falla, las anteriores podrían haberse creado.
                # Idealmente, esto se manejaría con una transacción.
                # (El save del form ya está dentro de un @transaction.atomic en la vista)
                self.add_error(None, e) # Añade error no ligado a un campo específico
                return [] # Detener y no devolver reservas parciales
        
        return reservas_creadas

class FechaSeleccionForm(forms.Form):
    """
    Formulario simple para seleccionar una fecha.
    """
    fecha = forms.DateField(
        label="Seleccione una fecha para agendar",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date()
    )

    def clean_fecha(self):
        data = self.cleaned_data['fecha']
        if data < timezone.now().date():
            raise forms.ValidationError("No puede seleccionar una fecha pasada.")
        # Podrías añadir más validaciones, como no permitir fines de semana, etc.
        return data