# agendamiento/admin.py
from django.contrib import admin
from .models import Vehiculo, UsuarioSistema, Reserva

@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    """
    Configuración del panel de administración para el modelo Vehiculo.
    """
    list_display = ('patente', 'marca', 'modelo', 'tipo_vehiculo', 'razon_social', 'rut', 'estado')
    search_fields = ('patente', 'marca', 'modelo', 'razon_social', 'rut')
    list_filter = ('marca', 'modelo', 'tipo_vehiculo', 'razon_social', 'estado')
    ordering = ('marca', 'modelo', 'patente')
    # raw_id_fields = () # Para campos ForeignKey o ManyToManyField con muchas opciones

    fieldsets = (
        ('Información Principal', {
            'fields': ('patente', 'marca', 'modelo', 'tipo_vehiculo')
        }),
        ('Empresa Propietaria', {
            'fields': ('razon_social', 'razon_social2', 'rut')
        }),
        ('Detalles Adicionales', {
            'fields': ('tipo_transmision', 'estado'),
            'classes': ('collapse',) # Para que aparezca colapsado por defecto
        }),
    )

@admin.register(UsuarioSistema)
class UsuarioSistemaAdmin(admin.ModelAdmin):
    """
    Configuración del panel de administración para el modelo UsuarioSistema.
    """
    list_display = ('nombre_usuario_completo', 'user_email', 'razon_social_empresa', 'rut_empresa', 'ciudad')
    search_fields = ('nombre_usuario_completo', 'user__username', 'user__email', 'razon_social_empresa', 'rut_empresa')
    list_filter = ('razon_social_empresa', 'ciudad')
    ordering = ('nombre_usuario_completo',)
    raw_id_fields = ('user',) # Facilita la selección del usuario Django

    fieldsets = (
        ('Información del Usuario', {
            'fields': ('user', 'nombre_usuario_completo')
        }),
        ('Información de la Empresa Asignada', {
            'fields': ('razon_social_empresa', 'razon_social2_empresa', 'rut_empresa', 'ciudad')
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email Usuario Django'
    user_email.admin_order_field = 'user__email'


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    """
    Configuración del panel de administración para el modelo Reserva.
    """
    list_display = ('vehiculo_info', 'usuario_info', 'fecha_reserva', 'hora_inicio_reserva', 'hora_fin_reserva')
    search_fields = (
        'vehiculo__patente', 'vehiculo__marca', 'vehiculo__modelo',
        'usuario__nombre_usuario_completo', 'usuario__user__username',
        'fecha_reserva'
    )
    list_filter = ('fecha_reserva', 'vehiculo__razon_social', 'vehiculo__marca', 'usuario__razon_social_empresa')
    ordering = ('-fecha_reserva', '-hora_inicio_reserva')
    date_hierarchy = 'fecha_reserva' # Permite navegar por fechas
    # raw_id_fields = ('vehiculo', 'usuario')

    fieldsets = (
        (None, {
            'fields': ('vehiculo', 'usuario')
        }),
        ('Horario de Reserva', {
            'fields': ('fecha_reserva', 'hora_inicio_reserva') # hora_fin_reserva se calcula
        }),
    )
    # readonly_fields = ('hora_fin_reserva',) # Para mostrarlo pero no editarlo

    def vehiculo_info(self, obj):
        return f"{obj.vehiculo.marca} {obj.vehiculo.modelo} ({obj.vehiculo.patente})"
    vehiculo_info.short_description = 'Vehículo'
    vehiculo_info.admin_order_field = 'vehiculo__patente'

    def usuario_info(self, obj):
        return obj.usuario.nombre_usuario_completo
    usuario_info.short_description = 'Usuario'
    usuario_info.admin_order_field = 'usuario__nombre_usuario_completo'

    # No permitir agregar reservas desde el admin si se quiere forzar la lógica de negocio de la UI
    # def has_add_permission(self, request):
    #     return False

    # No permitir cambiar reservas desde el admin si se quiere forzar la lógica de negocio
    # def has_change_permission(self, request, obj=None):
    #     return False