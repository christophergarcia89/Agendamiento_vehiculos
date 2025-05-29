# agendamiento/management/commands/load_csv_data.py
import csv
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from agendamiento.models import Vehiculo, UsuarioSistema
from django.contrib.auth.models import User
from django.utils import timezone
import re # Para validaciones
from datetime import time

class Command(BaseCommand):
    help = 'Carga datos desde un archivo CSV a los modelos Vehiculo o UsuarioSistema.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='La ruta completa al archivo CSV.')
        parser.add_argument('model_name', type=str, help='El nombre del modelo a cargar (Vehiculo o UsuarioSistema).')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        model_name = options['model_name'].lower()

        if model_name not in ['vehiculo', 'usuariosistema']:
            raise CommandError(f"Nombre de modelo '{model_name}' no válido. Use 'Vehiculo' o 'UsuarioSistema'.")

        try:
            with open(csv_file_path, mode='r', encoding='utf-8-sig') as file: # utf-8-sig para manejar BOM
                reader = csv.DictReader(file)
                
                if model_name == 'vehiculo':
                    self._load_vehiculos(reader)
                elif model_name == 'usuariosistema':
                    self._load_usuarios_sistema(reader)

        except FileNotFoundError:
            raise CommandError(f"Archivo no encontrado: {csv_file_path}")
        except Exception as e:
            raise CommandError(f"Error procesando el archivo CSV: {e}")

    def _clean_rut(self, rut_str):
        if not rut_str:
            return None
        # Limpiar y formatear RUT si es necesario, ejemplo básico
        rut_str = rut_str.replace('.', '').replace('-', '').strip().upper()
        if not rut_str: return None
        
        cuerpo = rut_str[:-1]
        dv = rut_str[-1]
        
        # Formatear cuerpo con puntos
        cuerpo_formateado = ""
        if len(cuerpo) > 0:
            cuerpo_formateado = cuerpo[-3:]
            cuerpo = cuerpo[:-3]
        if len(cuerpo) > 0:
            cuerpo_formateado = cuerpo[-3:] + "." + cuerpo_formateado
            cuerpo = cuerpo[:-3]
        if len(cuerpo) > 0:
            cuerpo_formateado = cuerpo + "." + cuerpo_formateado
        
        return f"{cuerpo_formateado}-{dv}" if cuerpo_formateado else None


    def _clean_patente(self, patente_str):
        if not patente_str:
            return None
        patente_str = patente_str.strip().upper()
        # Validar y/o formatear patente si es necesario
        # Ejemplo: asegurar que tenga un guion si es el formato esperado
        if re.match(r'^[A-Z0-9]{4}[A-Z0-9]{2}$', patente_str) and len(patente_str) == 6: # Ej: RFWB77
             patente_str = f"{patente_str[:4]}-{patente_str[4:]}" # RFWB-77
        elif re.match(r'^[A-Z0-9]{2}[A-Z0-9]{2}[A-Z0-9]{2}$', patente_str) and len(patente_str) == 6: # Ej: RF WB 77 (sin espacios)
             patente_str = f"{patente_str[:2]}-{patente_str[2:4]}-{patente_str[4:]}"
        
        # Re-validar con el regex del modelo
        if not re.match(r'^[A-Z0-9]{2,4}-[A-Z0-9]{2,4}$', patente_str):
            if not re.match(r'^[A-Z0-9]+(?:-[A-Z0-9]+)*$', patente_str): # Formato más genérico
                self.stdout.write(self.style.WARNING(f"Formato de patente '{patente_str}' podría ser inválido. Se intentará guardar."))
        return patente_str


    @transaction.atomic
    def _load_vehiculos(self, reader):
        self.stdout.write(self.style.SUCCESS("Iniciando carga de Vehículos..."))
        # Mapeo esperado de columnas CSV a campos del modelo Vehiculo
        # CSV: RAZON SOCIAL,RAZON SOCIAL2,RUT,PATENTE,TIPO VEHICULO,MARCA,MODELO,TIPO,ESTADO
        # Modelo: razon_social, razon_social2, rut, patente, tipo_vehiculo, marca, modelo, tipo_transmision, estado
        
        required_columns = ['RAZON SOCIAL', 'RUT', 'PATENTE', 'TIPO VEHICULO', 'MARCA', 'MODELO', 'TIPO']
        
        # Verificar que todas las columnas requeridas estén en el CSV
        if not all(col in reader.fieldnames for col in required_columns):
            missing = [col for col in required_columns if col not in reader.fieldnames]
            raise CommandError(f"Columnas CSV faltantes para Vehiculo: {', '.join(missing)}. Columnas disponibles: {', '.join(reader.fieldnames)}")

        count_created = 0
        count_updated = 0
        count_skipped = 0

        for i, row in enumerate(reader):
            patente = self._clean_patente(row.get('PATENTE', '').strip())
            if not patente:
                self.stdout.write(self.style.WARNING(f"Fila {i+2}: Patente faltante. Se omite esta fila."))
                count_skipped += 1
                continue

            rut_empresa = self._clean_rut(row.get('RUT', '').strip())
            if not rut_empresa:
                self.stdout.write(self.style.WARNING(f"Fila {i+2} (Patente: {patente}): RUT faltante. Se omite esta fila."))
                count_skipped += 1
                continue
            
            razon_social = row.get('RAZON SOCIAL', '').strip()
            if not razon_social:
                self.stdout.write(self.style.WARNING(f"Fila {i+2} (Patente: {patente}): RAZON SOCIAL faltante. Se omite esta fila."))
                count_skipped += 1
                continue

            vehiculo_data = {
                'razon_social': razon_social,
                'razon_social2': row.get('RAZON SOCIAL2', '').strip() or None,
                'rut': rut_empresa,
                'tipo_vehiculo': row.get('TIPO VEHICULO', '').strip(),
                'marca': row.get('MARCA', '').strip(),
                'modelo': row.get('MODELO', '').strip(),
                'tipo_transmision': row.get('TIPO', '').strip(), # 'TIPO' en CSV es 'tipo_transmision' en modelo
                'estado': row.get('ESTADO', '').strip() or None,
            }

            try:
                vehiculo, created = Vehiculo.objects.update_or_create(
                    patente=patente,
                    defaults=vehiculo_data
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Vehículo '{vehiculo.patente}' creado."))
                    count_created += 1
                else:
                    self.stdout.write(self.style.NOTICE(f"Vehículo '{vehiculo.patente}' actualizado."))
                    count_updated += 1
            except IntegrityError as e:
                self.stdout.write(self.style.ERROR(f"Error de integridad al procesar vehículo con patente '{patente}': {e}. Se omite."))
                count_skipped += 1
            except ValidationError as e:
                self.stdout.write(self.style.ERROR(f"Error de validación para vehículo con patente '{patente}': {e.message_dict}. Se omite."))
                count_skipped += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error inesperado para vehículo con patente '{patente}': {e}. Se omite."))
                count_skipped += 1
        
        self.stdout.write(self.style.SUCCESS(f"Carga de Vehículos completada. Creados: {count_created}, Actualizados: {count_updated}, Omitidos: {count_skipped}."))

    @transaction.atomic
    def _load_usuarios_sistema(self, reader):
        self.stdout.write(self.style.SUCCESS("Iniciando carga de Usuarios del Sistema..."))
        # Mapeo esperado de columnas CSV a campos del modelo UsuarioSistema
        # CSV: USUARIO,RAZON SOCIAL,RAZON SOCIAL2,RUT,CIUDAD
        # Modelo: user (Django User), nombre_usuario_completo, razon_social_empresa, razon_social2_empresa, rut_empresa, ciudad

        required_columns = ['USUARIO', 'RAZON SOCIAL', 'RUT', 'CIUDAD']
        if not all(col in reader.fieldnames for col in required_columns):
            missing = [col for col in required_columns if col not in reader.fieldnames]
            raise CommandError(f"Columnas CSV faltantes para UsuarioSistema: {', '.join(missing)}. Columnas disponibles: {', '.join(reader.fieldnames)}")

        count_created = 0
        count_updated = 0
        count_skipped = 0

        for i, row in enumerate(reader):
            nombre_usuario_csv = row.get('USUARIO', '').strip() # Este es el nombre completo, ej: "RICARDO CLAVIJO"
            if not nombre_usuario_csv:
                self.stdout.write(self.style.WARNING(f"Fila {i+2}: Nombre de USUARIO CSV faltante. Se omite esta fila."))
                count_skipped += 1
                continue
            
            # Crear un nombre de usuario Django único a partir del nombre completo
            # Esto es una simplificación. En un caso real, se necesitaría una estrategia más robusta
            # para generar nombres de usuario únicos y contraseñas seguras.
            username_base = "".join(nombre_usuario_csv.split()).lower()
            username = username_base
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"
                counter += 1
            
            rut_empresa = self._clean_rut(row.get('RUT', '').strip())
            if not rut_empresa:
                self.stdout.write(self.style.WARNING(f"Fila {i+2} (Usuario: {nombre_usuario_csv}): RUT de empresa faltante. Se omite esta fila."))
                count_skipped += 1
                continue

            razon_social_empresa = row.get('RAZON SOCIAL', '').strip()
            if not razon_social_empresa:
                self.stdout.write(self.style.WARNING(f"Fila {i+2} (Usuario: {nombre_usuario_csv}): RAZON SOCIAL de empresa faltante. Se omite esta fila."))
                count_skipped += 1
                continue

            # Intentar obtener el usuario Django o crearlo
            # Para este ejemplo, crearemos un usuario Django si no existe.
            # Se asume que el email podría ser username@example.com o similar.
            # ¡IMPORTANTE! En producción, la creación de usuarios y manejo de contraseñas debe ser seguro.
            try:
                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'first_name': nombre_usuario_csv.split(' ')[0] if ' ' in nombre_usuario_csv else nombre_usuario_csv,
                        'last_name': ' '.join(nombre_usuario_csv.split(' ')[1:]) if ' ' in nombre_usuario_csv else '',
                        'email': f"{username}@example.com" # Email de placeholder
                    }
                )
                if user_created:
                    user.set_password('password123') # ¡Contraseña insegura! Solo para ejemplo.
                    user.save()
                    self.stdout.write(self.style.NOTICE(f"Usuario Django '{user.username}' creado con contraseña temporal."))
            except IntegrityError: # Por si el username ya existe pero con diferentes defaults (raro aquí)
                 self.stdout.write(self.style.ERROR(f"Error creando usuario Django para '{nombre_usuario_csv}'. Ya existe o hay conflicto. Se omite."))
                 count_skipped += 1
                 continue


            usuario_sistema_data = {
                'nombre_usuario_completo': nombre_usuario_csv,
                'razon_social_empresa': razon_social_empresa,
                'razon_social2_empresa': row.get('RAZON SOCIAL2', '').strip() or None,
                'rut_empresa': rut_empresa,
                'ciudad': row.get('CIUDAD', '').strip(),
            }

            try:
                # Usar user (el objeto User de Django) para la relación
                perfil, created = UsuarioSistema.objects.update_or_create(
                    user=user,
                    defaults=usuario_sistema_data
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Perfil UsuarioSistema para '{perfil.nombre_usuario_completo}' ({user.username}) creado."))
                    count_created += 1
                else:
                    self.stdout.write(self.style.NOTICE(f"Perfil UsuarioSistema para '{perfil.nombre_usuario_completo}' ({user.username}) actualizado."))
                    count_updated += 1
            except IntegrityError as e: # Podría ocurrir si se intenta crear un UsuarioSistema para un User que ya tiene uno.
                self.stdout.write(self.style.ERROR(f"Error de integridad al procesar UsuarioSistema para '{nombre_usuario_csv}': {e}. Se omite."))
                count_skipped += 1
            except ValidationError as e:
                self.stdout.write(self.style.ERROR(f"Error de validación para UsuarioSistema '{nombre_usuario_csv}': {e.message_dict}. Se omite."))
                count_skipped += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error inesperado para UsuarioSistema '{nombre_usuario_csv}': {e}. Se omite."))
                count_skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Carga de Usuarios del Sistema completada. Creados: {count_created}, Actualizados: {count_updated}, Omitidos: {count_skipped}."))