"""
Repositorio SQL puro para el módulo de reservas, disponibilidad, estados de reserva,
auditoría (HISTORIAL_RESERVAS), pagos (administrador y cliente en línea),
gestión de empresas/sucursales/canchas y creación de reservas administrativas.
"""

from django.contrib.auth.hashers import make_password
from reservacancha_proj.db import db_transaction, fetch_all_dicts


class ReservaRepository:
    """Ejecuta sentencias parametrizadas en SQL Server sin emplear ORM."""

    @staticmethod
    def listar_canchas_activas():
        """Devuelve todas las canchas activas junto con su sucursal y tipo de deporte."""
        sql = """
            SELECT c.id_cancha, c.nombre AS cancha, c.ubicacion_interna, c.precio_hora,
                   s.id_sucursal, s.nombre_sucursal, tc.nombre AS tipo_deporte
            FROM CANCHAS c
            JOIN SUCURSALES s ON c.id_sucursal = s.id_sucursal
            JOIN TIPOS_CANCHA tc ON c.id_tipo_cancha = tc.id_tipo_cancha
            WHERE c.activa = 1 AND s.activa = 1
            ORDER BY s.nombre_sucursal, c.nombre
        """
        with db_transaction() as cursor:
            cursor.execute(sql)
            return fetch_all_dicts(cursor)

    @staticmethod
    def obtener_horarios_disponibles(id_cancha: int, fecha_reserva: str):
        """
        Consulta los bloques horarios de la sucursal de la cancha que no estén ocupados
        en la fecha indicada por reservas cuyo estado tenga ocupa_horario = 1 en ESTADOS_RESERVA.
        """
        sql = """
            SELECT h.id_horario,
                   CONVERT(VARCHAR(5), h.hora_inicio, 108) AS inicio,
                   CONVERT(VARCHAR(5), h.hora_fin, 108) AS fin
            FROM HORARIOS h
            JOIN CANCHAS c ON h.id_sucursal = c.id_sucursal
            WHERE c.id_cancha = ?
              AND h.id_horario NOT IN (
                  SELECT r.id_horario
                  FROM RESERVAS r
                  JOIN ESTADOS_RESERVA er ON r.id_estado_reserva = er.id_estado_reserva
                  WHERE r.id_cancha = ?
                    AND r.fecha_reserva = ?
                    AND er.ocupa_horario = 1
              )
            ORDER BY h.hora_inicio
        """
        with db_transaction() as cursor:
            cursor.execute(sql, (id_cancha, id_cancha, fecha_reserva))
            return fetch_all_dicts(cursor)

    @staticmethod
    def crear_reserva(
        id_cliente: int, id_cancha: int, id_horario: int, fecha_reserva: str
    ):
        """
        Crea una reserva en estado 'pendiente', congela el precio de la cancha
        y registra el evento inicial en HISTORIAL_RESERVAS dentro de una transacción.
        """
        with db_transaction() as cursor:
            cursor.execute(
                "SELECT precio_hora FROM CANCHAS WHERE id_cancha = ? AND activa = 1",
                (id_cancha,),
            )
            cancha = cursor.fetchone()
            if not cancha:
                raise ValueError("La cancha no está disponible.")
            precio = cancha[0]

            cursor.execute(
                "SELECT id_estado_reserva FROM ESTADOS_RESERVA WHERE nombre_estado = 'pendiente'"
            )
            estado_row = cursor.fetchone()
            if not estado_row:
                raise ValueError("No existe el estado 'pendiente' en ESTADOS_RESERVA.")
            id_estado_pendiente = estado_row[0]

            sql_ins = """
                INSERT INTO RESERVAS (
                    id_cliente, id_cancha, id_horario, id_estado_reserva,
                    fecha_reserva, monto_acordado
                )
                OUTPUT INSERTED.id_reserva
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor.execute(
                sql_ins,
                (
                    id_cliente,
                    id_cancha,
                    id_horario,
                    id_estado_pendiente,
                    fecha_reserva,
                    precio,
                ),
            )
            id_reserva = cursor.fetchone()[0]

            sql_hist = """
                INSERT INTO HISTORIAL_RESERVAS (
                    id_reserva, id_usuario_admin, id_estado_anterior, id_estado_nuevo,
                    fecha_anterior, fecha_nueva, id_horario_anterior, id_horario_nuevo,
                    motivo_cambio
                )
                VALUES (?, NULL, NULL, ?, NULL, ?, NULL, ?, 'Reserva creada por el cliente')
            """
            cursor.execute(
                sql_hist, (id_reserva, id_estado_pendiente, fecha_reserva, id_horario)
            )
            return id_reserva

    @staticmethod
    def listar_reservas_cliente(id_cliente: int):
        """
        Lista las reservas del cliente con estado, saldos e indicador de cancelación
        (requiere al menos 3 días de anticipación respecto a la fecha actual).
        """
        sql = """
            SELECT r.id_reserva, s.nombre_sucursal, c.nombre AS cancha,
                   CONVERT(VARCHAR(10), r.fecha_reserva, 120) AS fecha_reserva,
                   CONVERT(VARCHAR(5), h.hora_inicio, 108) AS hora_inicio,
                   CONVERT(VARCHAR(5), h.hora_fin, 108) AS hora_fin,
                   er.nombre_estado AS estado, r.monto_acordado,
                   v.total_pagado, v.saldo_pendiente,
                   DATEDIFF(DAY, CAST(GETDATE() AS DATE), r.fecha_reserva) AS dias_anticipacion
            FROM RESERVAS r
            JOIN ESTADOS_RESERVA er ON r.id_estado_reserva = er.id_estado_reserva
            JOIN CANCHAS c ON r.id_cancha = c.id_cancha
            JOIN SUCURSALES s ON c.id_sucursal = s.id_sucursal
            JOIN HORARIOS h ON r.id_horario = h.id_horario
            JOIN vw_estado_cuenta_reservas v ON r.id_reserva = v.id_reserva
            WHERE r.id_cliente = ?
            ORDER BY r.fecha_reserva DESC, h.hora_inicio ASC
        """
        with db_transaction() as cursor:
            cursor.execute(sql, (id_cliente,))
            filas = fetch_all_dicts(cursor)
            for f in filas:
                estado_actual = (f["estado"] or "").lower()
                dias = f["dias_anticipacion"]
                f["puede_cancelar"] = (
                    estado_actual in ("pendiente", "confirmada")
                    and dias is not None
                    and dias >= 3
                )
            return filas

    @staticmethod
    def cancelar_reserva_cliente(
        id_reserva: int,
        id_cliente: int,
        motivo: str = "Cancelada por el cliente con >= 3 días de anticipación",
    ):
        """
        Cancela la reserva del cliente si falta al menos 3 días para la fecha reservada.
        Al pasar a 'cancelada' (ocupa_horario = 0), el horario vuelve a quedar libre
        y se deja constancia en HISTORIAL_RESERVAS con id_usuario_admin = NULL.
        """
        with db_transaction() as cursor:
            sql_sel = """
                SELECT r.id_estado_reserva, r.fecha_reserva, r.id_horario,
                       er.nombre_estado,
                       DATEDIFF(DAY, CAST(GETDATE() AS DATE), r.fecha_reserva) AS dias_anticipacion
                FROM RESERVAS r
                JOIN ESTADOS_RESERVA er ON r.id_estado_reserva = er.id_estado_reserva
                WHERE r.id_reserva = ? AND r.id_cliente = ?
            """
            cursor.execute(sql_sel, (id_reserva, id_cliente))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Reserva no encontrada para este cliente.")

            estado_actual = (row[3] or "").lower()
            dias = row[4]
            if estado_actual == "cancelada":
                raise ValueError("La reserva ya está cancelada.")
            if dias is None or dias < 3:
                raise ValueError(
                    "Solo puedes cancelar reservas con al menos 3 días de anticipación."
                )

            cursor.execute(
                "SELECT id_estado_reserva FROM ESTADOS_RESERVA WHERE LOWER(nombre_estado) = 'cancelada'"
            )
            estado_canc = cursor.fetchone()
            if not estado_canc:
                raise ValueError("No existe el estado 'cancelada' en ESTADOS_RESERVA.")
            id_estado_cancelada = estado_canc[0]

            cursor.execute(
                "UPDATE RESERVAS SET id_estado_reserva = ? WHERE id_reserva = ?",
                (id_estado_cancelada, id_reserva),
            )

            sql_hist = """
                INSERT INTO HISTORIAL_RESERVAS (
                    id_reserva, id_usuario_admin, id_estado_anterior, id_estado_nuevo,
                    fecha_anterior, fecha_nueva, id_horario_anterior, id_horario_nuevo,
                    motivo_cambio
                )
                VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)
            """
            motivo_limpio = (
                motivo.strip()
                if motivo and motivo.strip()
                else "Cancelada por el cliente con >= 3 días de anticipación"
            )
            cursor.execute(
                sql_hist,
                (
                    id_reserva,
                    row[0],
                    id_estado_cancelada,
                    row[1],
                    row[1],
                    row[2],
                    row[2],
                    motivo_limpio,
                ),
            )

    @staticmethod
    def registrar_pago_cliente(
        id_reserva: int,
        id_cliente: int,
        id_metodo_pago: int,
        monto: float,
        titular_tarjeta: str = "",
        ultimos4: str = "",
        num_autorizacion: str = "",
        banco_emisor: str = "",
    ):
        """Registra un pago en línea efectuado por el cliente sobre su reserva."""
        with db_transaction() as cursor:
            cursor.execute(
                """
                SELECT v.saldo_pendiente
                FROM vw_estado_cuenta_reservas v
                JOIN RESERVAS r ON v.id_reserva = r.id_reserva
                WHERE v.id_reserva = ? AND r.id_cliente = ?
                """,
                (id_reserva, id_cliente),
            )
            cuenta = cursor.fetchone()
            if not cuenta or monto <= 0 or monto > float(cuenta[0]):
                raise ValueError("Monto inválido o superior al saldo pendiente.")

            id_comprobante = None
            ref_auth = num_autorizacion.strip() if num_autorizacion else ""
            if not ref_auth and ultimos4.strip():
                ref_auth = f"CARD-****{ultimos4.strip()[-4:]}"

            detalle_banco = banco_emisor.strip() if banco_emisor else ""
            if titular_tarjeta.strip():
                detalle_banco = f"{detalle_banco} ({titular_tarjeta.strip()})".strip()

            if ref_auth or detalle_banco:
                cursor.execute(
                    """
                    INSERT INTO COMPROBANTES_PAGO (numero_autorizacion, banco_emisor)
                    OUTPUT INSERTED.id_comprobante
                    VALUES (?, ?)
                    """,
                    (ref_auth or "PAGO-ONLINE", detalle_banco or None),
                )
                id_comprobante = cursor.fetchone()[0]

            cursor.execute(
                "SELECT id_estado_pago FROM ESTADOS_PAGO WHERE nombre_estado = 'Aprobado'"
            )
            estado_pago_row = cursor.fetchone()
            id_estado_aprobado = estado_pago_row[0] if estado_pago_row else 1

            cursor.execute(
                """
                INSERT INTO PAGOS (
                    id_reserva, id_metodo_pago, id_estado_pago,
                    id_comprobante, id_usuario_admin, monto
                )
                VALUES (?, ?, ?, ?, NULL, ?)
                """,
                (id_reserva, id_metodo_pago, id_estado_aprobado, id_comprobante, monto),
            )

    @staticmethod
    def listar_estados_reserva():
        """Lista los estados activos de reserva desde ESTADOS_RESERVA."""
        with db_transaction() as cursor:
            cursor.execute(
                "SELECT id_estado_reserva, nombre_estado FROM ESTADOS_RESERVA WHERE activo = 1 ORDER BY id_estado_reserva"
            )
            return fetch_all_dicts(cursor)

    @staticmethod
    def listar_metodos_pago():
        """Lista los métodos de pago activos desde METODOS_PAGO."""
        with db_transaction() as cursor:
            cursor.execute(
                "SELECT id_metodo_pago, nombre FROM METODOS_PAGO WHERE activo = 1 ORDER BY id_metodo_pago"
            )
            return fetch_all_dicts(cursor)

    @staticmethod
    def listar_clientes_resumen():
        """Lista clientes registrados para seleccionar uno existente en el panel admin."""
        sql = """
            SELECT id_cliente, primer_nombre, segundo_nombre, primer_apellido,
                   segundo_apellido, correo, telefono
            FROM CLIENTES
            ORDER BY primer_apellido, primer_nombre
        """
        with db_transaction() as cursor:
            cursor.execute(sql)
            return fetch_all_dicts(cursor)

    @staticmethod
    def crear_reserva_admin(
        id_admin: int,
        id_cancha: int,
        id_horario: int,
        fecha_reserva: str,
        id_cliente_existente=None,
        nuevo_cliente: dict = None,
    ):
        """
        Crea una reserva desde el panel administrativo usando un cliente existente
        o registrando uno nuevo de forma atómica en la misma transacción.
        """
        with db_transaction() as cursor:
            if id_cliente_existente:
                id_cliente = int(id_cliente_existente)
            elif nuevo_cliente:
                correo = (nuevo_cliente.get("correo") or "").strip().lower()
                if not correo:
                    raise ValueError("Debes indicar un correo para el nuevo cliente.")

                cursor.execute(
                    "SELECT id_cliente FROM CLIENTES WHERE LOWER(correo) = ?",
                    (correo,),
                )
                existente = cursor.fetchone()
                if existente:
                    id_cliente = existente[0]
                else:
                    pwd_hash = make_password(nuevo_cliente.get("password") or "123456")
                    cursor.execute(
                        """
                        INSERT INTO CLIENTES (
                            primer_nombre, segundo_nombre, primer_apellido, segundo_apellido,
                            telefono, correo, password_hash
                        )
                        OUTPUT INSERTED.id_cliente
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            nuevo_cliente["primer_nombre"].strip(),
                            nuevo_cliente.get("segundo_nombre", "").strip() or None,
                            nuevo_cliente["primer_apellido"].strip(),
                            nuevo_cliente.get("segundo_apellido", "").strip() or None,
                            nuevo_cliente["telefono"].strip(),
                            correo,
                            pwd_hash,
                        ),
                    )
                    id_cliente = cursor.fetchone()[0]
            else:
                raise ValueError(
                    "Selecciona un cliente existente o completa los datos de un cliente nuevo."
                )

            cursor.execute(
                "SELECT precio_hora FROM CANCHAS WHERE id_cancha = ? AND activa = 1",
                (id_cancha,),
            )
            cancha = cursor.fetchone()
            if not cancha:
                raise ValueError("La cancha no está activa o no existe.")
            precio = cancha[0]

            cursor.execute(
                "SELECT id_estado_reserva FROM ESTADOS_RESERVA WHERE LOWER(nombre_estado) = 'confirmada'"
            )
            est = cursor.fetchone()
            if not est:
                raise ValueError("No existe el estado 'confirmada' en ESTADOS_RESERVA.")
            id_estado_confirmada = est[0]

            cursor.execute(
                """
                INSERT INTO RESERVAS (
                    id_cliente, id_cancha, id_horario, id_estado_reserva,
                    fecha_reserva, monto_acordado
                )
                OUTPUT INSERTED.id_reserva
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    id_cliente,
                    id_cancha,
                    id_horario,
                    id_estado_confirmada,
                    fecha_reserva,
                    precio,
                ),
            )
            id_reserva = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO HISTORIAL_RESERVAS (
                    id_reserva, id_usuario_admin, id_estado_anterior, id_estado_nuevo,
                    fecha_anterior, fecha_nueva, id_horario_anterior, id_horario_nuevo,
                    motivo_cambio
                )
                VALUES (?, ?, NULL, ?, NULL, ?, NULL, ?, 'Reserva creada desde panel administrativo')
                """,
                (id_reserva, id_admin, id_estado_confirmada, fecha_reserva, id_horario),
            )
            return id_reserva

    @staticmethod
    def listar_empresas():
        """Lista empresas registradas para el Super Admin."""
        with db_transaction() as cursor:
            cursor.execute(
                "SELECT id_empresa, nombre_fiscal, rtn_nit, correo_contacto FROM EMPRESAS ORDER BY nombre_fiscal"
            )
            return fetch_all_dicts(cursor)

    @staticmethod
    def crear_empresa(nombre_fiscal: str, rtn_nit: str, correo_contacto: str):
        """Crea una nueva empresa en EMPRESAS (Super Admin)."""
        with db_transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO EMPRESAS (nombre_fiscal, rtn_nit, correo_contacto)
                VALUES (?, ?, ?)
                """,
                (
                    nombre_fiscal.strip(),
                    rtn_nit.strip(),
                    correo_contacto.strip().lower(),
                ),
            )

    @staticmethod
    def crear_sucursal(
        id_empresa: int, nombre_sucursal: str, direccion: str, telefono: str
    ):
        """Crea una nueva sucursal asociada a una empresa (Super Admin)."""
        with db_transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO SUCURSALES (id_empresa, nombre_sucursal, direccion, telefono, activa)
                VALUES (?, ?, ?, ?, 1)
                """,
                (
                    id_empresa,
                    nombre_sucursal.strip(),
                    direccion.strip(),
                    telefono.strip(),
                ),
            )

    @staticmethod
    def listar_sucursales_y_tipos():
        """Lista sucursales activas y tipos de cancha."""
        with db_transaction() as cursor:
            cursor.execute(
                "SELECT id_sucursal, nombre_sucursal FROM SUCURSALES WHERE activa = 1 ORDER BY nombre_sucursal"
            )
            sucursales = fetch_all_dicts(cursor)

            cursor.execute(
                "SELECT id_tipo_cancha, nombre FROM TIPOS_CANCHA ORDER BY nombre"
            )
            tipos = fetch_all_dicts(cursor)

        return sucursales, tipos

    @staticmethod
    def listar_todas_las_canchas():
        """Lista todas las canchas de todas las sucursales."""
        sql = """
            SELECT c.id_cancha, c.nombre AS cancha, c.ubicacion_interna, c.precio_hora,
                   c.activa, s.nombre_sucursal, tc.nombre AS tipo_deporte
            FROM CANCHAS c
            JOIN SUCURSALES s ON c.id_sucursal = s.id_sucursal
            JOIN TIPOS_CANCHA tc ON c.id_tipo_cancha = tc.id_tipo_cancha
            ORDER BY s.nombre_sucursal, c.nombre
        """
        with db_transaction() as cursor:
            cursor.execute(sql)
            return fetch_all_dicts(cursor)

    @staticmethod
    def listar_canchas_por_sucursal(id_sucursal: int):
        """Lista las canchas de una sucursal específica."""
        sql = """
            SELECT c.id_cancha, c.nombre AS cancha, c.ubicacion_interna, c.precio_hora,
                   c.activa, s.nombre_sucursal, tc.nombre AS tipo_deporte
            FROM CANCHAS c
            JOIN SUCURSALES s ON c.id_sucursal = s.id_sucursal
            JOIN TIPOS_CANCHA tc ON c.id_tipo_cancha = tc.id_tipo_cancha
            WHERE c.id_sucursal = ?
            ORDER BY c.nombre
        """
        with db_transaction() as cursor:
            cursor.execute(sql, (id_sucursal,))
            return fetch_all_dicts(cursor)

    @staticmethod
    def crear_cancha(
        id_sucursal: int,
        id_tipo_cancha: int,
        nombre: str,
        ubicacion_interna: str,
        precio_hora: float,
    ):
        """Agrega una nueva cancha a la sucursal indicada."""
        if precio_hora <= 0:
            raise ValueError("El precio por hora debe ser mayor a cero.")

        sql = """
            INSERT INTO CANCHAS (
                id_sucursal, id_tipo_cancha, nombre, ubicacion_interna, precio_hora, activa
            )
            VALUES (?, ?, ?, ?, ?, 1)
        """
        with db_transaction() as cursor:
            cursor.execute(
                sql,
                (
                    id_sucursal,
                    id_tipo_cancha,
                    nombre.strip(),
                    ubicacion_interna.strip() if ubicacion_interna else None,
                    precio_hora,
                ),
            )

    @staticmethod
    def listar_reservas_admin(id_sucursal=None):
        """
        Consulta vw_estado_cuenta_reservas. Si id_sucursal es None (Admin General),
        devuelve todas las sucursales; si tiene valor (Admin Sucursal), filtra su sede.
        """
        sql = """
            SELECT v.id_reserva, v.nombre_sucursal, v.cancha, v.cliente_nombre,
                   CONVERT(VARCHAR(10), v.fecha_reserva, 120) AS fecha_reserva,
                   CONVERT(VARCHAR(5), v.hora_inicio, 108) AS hora_inicio,
                   CONVERT(VARCHAR(5), v.hora_fin, 108) AS hora_fin,
                   v.estado, r.id_estado_reserva, v.monto_acordado,
                   v.total_pagado, v.saldo_pendiente
            FROM vw_estado_cuenta_reservas v
            JOIN RESERVAS r ON v.id_reserva = r.id_reserva
            JOIN CANCHAS c ON r.id_cancha = c.id_cancha
        """
        params = ()
        if id_sucursal is not None:
            sql += " WHERE c.id_sucursal = ?"
            params = (id_sucursal,)
        sql += " ORDER BY v.fecha_reserva DESC, v.hora_inicio ASC"

        with db_transaction() as cursor:
            cursor.execute(sql, params)
            return fetch_all_dicts(cursor)

    @staticmethod
    def cambiar_estado_reserva(
        id_reserva: int, id_admin: int, id_estado_nuevo: int, motivo: str
    ):
        """Actualiza el estado de una reserva y deja constancia en HISTORIAL_RESERVAS."""
        with db_transaction() as cursor:
            cursor.execute(
                "SELECT id_estado_reserva, fecha_reserva, id_horario FROM RESERVAS WHERE id_reserva = ?",
                (id_reserva,),
            )
            actual = cursor.fetchone()
            if not actual:
                raise ValueError("Reserva no encontrada.")

            cursor.execute(
                "UPDATE RESERVAS SET id_estado_reserva = ? WHERE id_reserva = ?",
                (id_estado_nuevo, id_reserva),
            )

            sql_hist = """
                INSERT INTO HISTORIAL_RESERVAS (
                    id_reserva, id_usuario_admin, id_estado_anterior, id_estado_nuevo,
                    fecha_anterior, fecha_nueva, id_horario_anterior, id_horario_nuevo,
                    motivo_cambio
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(
                sql_hist,
                (
                    id_reserva,
                    id_admin,
                    actual[0],
                    id_estado_nuevo,
                    actual[1],
                    actual[1],
                    actual[2],
                    actual[2],
                    motivo.strip(),
                ),
            )

    @staticmethod
    def obtener_historial_reserva(id_reserva: int):
        """
        Recupera la auditoría de una reserva. Cuando id_usuario_admin es NULL,
        muestra 'Cliente' para distinguir acciones realizadas por el cliente.
        """
        sql = """
            SELECT h.id_historial,
                   ISNULL(ea.nombre_estado, 'NUEVA') AS estado_anterior,
                   en.nombre_estado AS estado_nuevo,
                   h.motivo_cambio,
                   CONVERT(VARCHAR(19), h.fecha_cambio, 120) AS fecha_cambio,
                   CASE
                       WHEN h.id_usuario_admin IS NULL THEN 'Cliente'
                       ELSE 'Admin: ' + u.primer_nombre + ' ' + u.primer_apellido
                   END AS responsable
            FROM HISTORIAL_RESERVAS h
            LEFT JOIN ESTADOS_RESERVA ea ON h.id_estado_anterior = ea.id_estado_reserva
            JOIN ESTADOS_RESERVA en ON h.id_estado_nuevo = en.id_estado_reserva
            LEFT JOIN USUARIOS_ADMINISTRADORES u ON h.id_usuario_admin = u.id_usuario
            WHERE h.id_reserva = ?
            ORDER BY h.fecha_cambio DESC
        """
        with db_transaction() as cursor:
            cursor.execute(sql, (id_reserva,))
            return fetch_all_dicts(cursor)

    @staticmethod
    def registrar_pago(
        id_reserva: int,
        id_metodo_pago: int,
        id_admin: int,
        monto: float,
        num_autorizacion: str = "",
        banco_emisor: str = "",
    ):
        """Registra un pago de forma atómica desde el panel administrativo."""
        with db_transaction() as cursor:
            cursor.execute(
                "SELECT saldo_pendiente FROM vw_estado_cuenta_reservas WHERE id_reserva = ?",
                (id_reserva,),
            )
            cuenta = cursor.fetchone()
            if not cuenta or monto <= 0 or monto > float(cuenta[0]):
                raise ValueError("Monto inválido o superior al saldo pendiente.")

            id_comprobante = None
            if num_autorizacion and num_autorizacion.strip():
                cursor.execute(
                    """
                    INSERT INTO COMPROBANTES_PAGO (numero_autorizacion, banco_emisor)
                    OUTPUT INSERTED.id_comprobante
                    VALUES (?, ?)
                    """,
                    (
                        num_autorizacion.strip(),
                        banco_emisor.strip() if banco_emisor else None,
                    ),
                )
                id_comprobante = cursor.fetchone()[0]

            cursor.execute(
                "SELECT id_estado_pago FROM ESTADOS_PAGO WHERE nombre_estado = 'Aprobado'"
            )
            estado_pago_row = cursor.fetchone()
            id_estado_aprobado = estado_pago_row[0] if estado_pago_row else 1

            cursor.execute(
                """
                INSERT INTO PAGOS (
                    id_reserva, id_metodo_pago, id_estado_pago,
                    id_comprobante, id_usuario_admin, monto
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    id_reserva,
                    id_metodo_pago,
                    id_estado_aprobado,
                    id_comprobante,
                    id_admin,
                    monto,
                ),
            )