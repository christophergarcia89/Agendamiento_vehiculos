# agendamiento/models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re

class Vehiculo(models.Model):
    """
    Modelo para representar los vehículos que se pueden agendar.
    """
    razon_social = models.CharField(max_length=255, verbose_name="Razón Social Principal")
    razon_social2 = models.CharField(max_length=255, blank=True, null=True, verbose_name="Razón Social Secundaria")
    rut = models.CharField(max_length=20, verbose_name="RUT Empresa") # Ej: "80.010.900-0"
    patente = models.CharField(max_length=10, unique=True, verbose_name="Patente") # Ej: "RFWB-77"
    tipo_vehiculo = models.CharField(max_length=255, verbose_name="Tipo de Vehículo")
    marca = models.CharField(max_length=100, verbose_name="Marca")
    modelo = models.CharField(max_length=100, verbose_name="Modelo")
    tipo_transmision = models.CharField(max_length=50, verbose_name="Tipo de Transmisión") # Nombre de columna original "TIPO"
    estado = models.CharField(max_length=100, blank=True, null=True, verbose_name="Estado") # Ej: 'Activo', 'Mantenimiento'

    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.patente}) - {self.razon_social}"

    def clean(self):
        # Validar formato de patente (ej: AAAA-11 o AA-AA-11 o AA-11-AA)
        if not re.match(r'^[A-Z0-9]{2,4}-[A-Z0-9]{2,4}$', self.patente.upper()):
            # Intenta un formato más genérico si el primero falla, permitiendo guiones
            if not re.match(r'^[A-Z0-9]+(?:-[A-Z0-9]+)*$', self.patente.upper()):
                 raise ValidationError({'patente': 'Formato de patente inválido. Use formatos como XXXX-XX, XX-XX-XX o XX-XX-XX.'})
        self.patente = self.patente.upper()

        # Validar formato de RUT (opcional, pero recomendado)
        # Aquí un ejemplo simple, se podría usar una librería para validación de RUT chileno
        if self.rut and not re.match(r'^\d{1,2}\.\d{3}\.\d{3}-[\dkK]$', self.rut):
            raise ValidationError({'rut': 'Formato de RUT inválido. Use XX.XXX.XXX-X.'})

    class Meta:
        verbose_name = "Vehículo"
        verbose_name_plural = "Vehículos"
        ordering = ['marca', 'modelo', 'patente']

class UsuarioSistema(models.Model):
    """
    Modelo para representar a los usuarios del sistema de agendamiento,
    extendiendo o relacionándose con el modelo User de Django.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil_sistema", verbose_name="Usuario Django")
    nombre_usuario_completo = models.CharField(max_length=255, verbose_name="Nombre Completo del Usuario") # Ej: "RICARDO CLAVIJO"
    razon_social_empresa = models.CharField(max_length=255, verbose_name="Razón Social Empresa Asignada")
    razon_social2_empresa = models.CharField(max_length=255, blank=True, null=True, verbose_name="Razón Social Secundaria Empresa")
    rut_empresa = models.CharField(max_length=20, verbose_name="RUT Empresa Asignada") # Ej: "80.010.900-0"
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad")

    def __str__(self):
        return f"{self.nombre_usuario_completo} ({self.razon_social_empresa})"

    def clean(self):
        # Validar formato de RUT (opcional)
        if self.rut_empresa and not re.match(r'^\d{1,2}\.\d{3}\.\d{3}-[\dkK]$', self.rut_empresa):
            raise ValidationError({'rut_empresa': 'Formato de RUT inválido para la empresa. Use XX.XXX.XXX-X.'})

    class Meta:
        verbose_name = "Usuario del Sistema"
        verbose_name_plural = "Usuarios del Sistema"
        ordering = ['nombre_usuario_completo']

class Reserva(models.Model):
    """
    Modelo para representar las reservas de vehículos.
    Cada reserva es para un bloque de 1 hora.
    """
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.CASCADE, related_name="reservas", verbose_name="Vehículo")
    usuario = models.ForeignKey(UsuarioSistema, on_delete=models.CASCADE, related_name="reservas_realizadas", verbose_name="Usuario que Reserva")
    # Alternativamente, si no se usa UsuarioSistema directamente para la reserva:
    # usuario_django = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reservas_django_user")
    fecha_reserva = models.DateField(verbose_name="Fecha de Reserva")
    hora_inicio_reserva = models.TimeField(verbose_name="Hora de Inicio") # Ej: 09:00
    hora_fin_reserva = models.TimeField(verbose_name="Hora de Fin")     # Ej: 10:00 (calculada)

    def __str__(self):
        return f"Reserva de {self.vehiculo.patente} por {self.usuario.nombre_usuario_completo} el {self.fecha_reserva} de {self.hora_inicio_reserva} a {self.hora_fin_reserva}"

    def clean(self):
        # Validar que la hora de fin sea exactamente 1 hora después de la hora de inicio
        if self.hora_inicio_reserva and self.hora_fin_reserva:
            from datetime import datetime, timedelta
            inicio_dt = datetime.combine(self.fecha_reserva, self.hora_inicio_reserva)
            fin_esperado_dt = inicio_dt + timedelta(hours=1)
            if self.hora_fin_reserva != fin_esperado_dt.time():
                raise ValidationError(
                    {'hora_fin_reserva': f"La hora de fin debe ser 1 hora después de la hora de inicio ({fin_esperado_dt.strftime('%H:%M')})."}
                )

        # Validar que no haya reservas duplicadas para el mismo vehículo y bloque horario
        reservas_existentes = Reserva.objects.filter(
            vehiculo=self.vehiculo,
            fecha_reserva=self.fecha_reserva,
            hora_inicio_reserva=self.hora_inicio_reserva
        ).exclude(pk=self.pk) # Excluir el objeto actual si se está actualizando

        if reservas_existentes.exists():
            raise ValidationError(
                f"El vehículo {self.vehiculo.patente} ya está reservado para el {self.fecha_reserva} a las {self.hora_inicio_reserva.strftime('%H:%M')}."
            )

    def save(self, *args, **kwargs):
        # Calcular hora_fin_reserva automáticamente si no se provee (o para asegurar consistencia)
        from datetime import datetime, timedelta
        if self.hora_inicio_reserva and not self.hora_fin_reserva:
            inicio_dt = datetime.combine(datetime.today(), self.hora_inicio_reserva) # Fecha es irrelevante para el cálculo delta
            self.hora_fin_reserva = (inicio_dt + timedelta(hours=1)).time()
        
        # Asegurar que la hora de fin sea 1 hora después del inicio
        # Esto es una doble verificación, ya que clean() también lo hace.
        # Es útil si save() se llama directamente sin pasar por clean() (ej. en carga masiva)
        if self.hora_inicio_reserva:
            inicio_datetime = datetime.combine(self.fecha_reserva, self.hora_inicio_reserva)
            fin_esperado_datetime = inicio_datetime + timedelta(hours=1)
            self.hora_fin_reserva = fin_esperado_datetime.time()

        self.full_clean() # Llama a clean() antes de guardar
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"
        ordering = ['fecha_reserva', 'hora_inicio_reserva', 'vehiculo']
        unique_together = ('vehiculo', 'fecha_reserva', 'hora_inicio_reserva') # Asegura unicidad a nivel de BD