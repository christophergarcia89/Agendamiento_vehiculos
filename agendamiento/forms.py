from django import forms
from .models import Reserva, Vehiculo
from django.utils import timezone
from datetime import time, date, timedelta, datetime
from django.core.exceptions import ValidationError
from django.utils import timezone

class ReservaForm(forms.Form):
    vehiculo_id = forms.IntegerField(widget=forms.HiddenInput())
    fecha_reserva = forms.DateField(widget=forms.HiddenInput())
    # bloques_seleccionados se añade dinámicamente

    def __init__(self, *args, **kwargs):
        self.vehiculo = kwargs.pop('vehiculo', None)
        self.fecha = kwargs.pop('fecha', None)
        self.usuario_sistema = kwargs.pop('usuario_sistema', None)
        super().__init__(*args, **kwargs) # Llamar a super() es buena práctica aquí

        print(f"\n[DEBUG ReservaForm.__init__] Iniciando para Vehículo: {self.vehiculo}, Fecha: {self.fecha}")

        if self.vehiculo and self.fecha:
            self.fields['vehiculo_id'].initial = self.vehiculo.id
            self.fields['fecha_reserva'].initial = self.fecha
            
            # Horarios de operación: 08:00 a 18:00 (configurable)
            HORARIOS_OPERACION = [time(h) for h in range(8, 18)] # 8 AM a 5 PM (último bloque empieza a las 17:00)
            print(f"[DEBUG ReservaForm.__init__] HORARIOS_OPERACION: {HORARIOS_OPERACION}")
            
            bloques_disponibles_choices = []
            
            # Obtener reservas existentes para este vehículo y fecha
            reservas_existentes_actuales = Reserva.objects.filter(
                vehiculo=self.vehiculo,
                fecha_reserva=self.fecha
            ).values_list('hora_inicio_reserva', flat=True)
            
            # Convertir a lista para facilitar la depuración y evitar múltiples accesos a la BD si es un QuerySet grande
            lista_horas_reservadas = list(reservas_existentes_actuales)
            print(f"[DEBUG ReservaForm.__init__] Horas ya reservadas (BD): {lista_horas_reservadas}")

            for hora_inicio in HORARIOS_OPERACION:
                hora_fin = (datetime.combine(date.today(), hora_inicio) + timedelta(hours=1)).time()
                label = f"{hora_inicio.strftime('%H:%M')} - {hora_fin.strftime('%H:%M')}"
                
                # Comprobar si esta hora_inicio está en la lista de horas ya reservadas
                if hora_inicio not in lista_horas_reservadas:
                    bloques_disponibles_choices.append((hora_inicio.strftime('%H:%M:%S'), label))
                    print(f"[DEBUG ReservaForm.__init__] Añadiendo choice disponible: {label}")
                else:
                    print(f"[DEBUG ReservaForm.__init__] Hora {hora_inicio.strftime('%H:%M')} ya está reservada, no se añade como choice.")
            
            print(f"[DEBUG ReservaForm.__init__] Choices generados para el formulario: {bloques_disponibles_choices}")
            
            if bloques_disponibles_choices:
                self.fields['bloques_seleccionados'] = forms.MultipleChoiceField(
                    choices=bloques_disponibles_choices,
                    widget=forms.CheckboxSelectMultiple,
                    label="Seleccione los bloques horarios",
                    required=True
                )
                print(f"[DEBUG ReservaForm.__init__] CAMPO 'bloques_seleccionados' CREADO con {len(bloques_disponibles_choices)} opciones.")
            else:
                print(f"[DEBUG ReservaForm.__init__] CAMPO 'bloques_seleccionados' NO CREADO porque la lista de choices disponibles está vacía.")
        else:
            print(f"[DEBUG ReservaForm.__init__] CAMPO 'bloques_seleccionados' NO CREADO porque self.vehiculo o self.fecha es None.")
        print("[DEBUG ReservaForm.__init__] Fin de inicialización.\n")


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