# ReservaCancha

Sistema web multi-empresa y multi-sucursal para la administración de canchas deportivas, consulta de disponibilidad horaria en tiempo real, gestión de reservas y pagos, y trazabilidad completa mediante auditoría.

## Arquitectura y características principales

- **Backend en Python y Django sin ORM:** uso de Django para enrutamiento, sesiones, protección CSRF, mensajes y plantillas HTML, combinado con consultas SQL parametrizadas mediante `pyodbc` y transacciones explícitas (`commit` / `rollback`).
- **Base de datos en SQL Server (3FN):** modelo normalizado de 15 tablas con atributos atómicos de nombres y apellidos, tablas de catálogo (`ESTADOS_RESERVA`, `METODOS_PAGO`, `ESTADOS_PAGO`, `ROLES_ADMIN`, `TIPOS_CANCHA`), congelamiento de tarifa (`monto_acordado`) y comprobantes de pago (`COMPROBANTES_PAGO`).
- **Prevención de colisiones y estado de cuenta:** vista indexada con `SCHEMABINDING` (`vw_reservas_activas_bloqueo`) e índice único agrupado para evitar dobles reservas activas, junto con la vista `vw_estado_cuenta_reservas` para calcular montos, pagos aprobados y saldos pendientes.
- **Control de acceso por roles (RBAC):**
  - **Cliente:** consulta canchas y horarios disponibles, crea reservas, revisa sus reservas y estados, realiza pagos en línea (incluyendo opciones de tarjeta) y cancela con al menos **3 días de anticipación** para liberar el cupo.
  - **Admin Sucursal:** administra reservas, estados, cobros e historial de su sucursal, crea reservas para clientes existentes o nuevos y agrega canchas en su sede.
  - **Admin General (Super Admin):** acceso global (`id_sucursal = NULL`) a reservas de todas las sedes y administración de empresas, sucursales y canchas.
- **Auditoría en `HISTORIAL_RESERVAS`:** registra cambios de estado, fecha, horario y motivo, distinguiendo acciones de administradores de las realizadas por el cliente.
- **Interfaz web:** construida con HTML5, Bootstrap 5 y JavaScript (`fetch` a endpoints JSON de disponibilidad y auditoría).

## Requisitos y puesta en marcha

1. **Requisitos:**
   - Python 3.x
   - Microsoft SQL Server y SQL Server Management Studio (SSMS)
   - Controlador ODBC para SQL Server
   - Paquetes Python: `django` y `pyodbc`

2. **Base de datos:**
   - Ejecuta el script DDL de `reserva_cancha` y los datos iniciales en SSMS.
   - Si los clientes registran pagos en línea sin administrador asignado, habilita `NULL` en `PAGOS.id_usuario_admin`.

3. **Conexión y ejecución:**
   - Ajusta la cadena de conexión en `reservacancha_proj/db.py` según tu instancia de SQL Server.
   - Desde la carpeta del proyecto (`manage.py`), ejecuta:

```bash
pip install django pyodbc
python manage.py migrate sessions
python manage.py runserver
