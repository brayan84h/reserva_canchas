"""
Repositorio de acceso a datos para usuarios (administradores y clientes) usando SQL puro.
Respeta la estructura en 3FN con atributos atómicos de nombre y apellido en CLIENTES.
"""

from django.contrib.auth.hashers import check_password, make_password
from reservacancha_proj.db import db_transaction, fetch_one_dict


class UserRepository:
    """Encapsula las operaciones SQL de autenticación y registro de usuarios."""

    @staticmethod
    def autenticar_usuario(correo: str, password_plano: str):
        """
        Valida credenciales primero en USUARIOS_ADMINISTRADORES y luego en CLIENTES.
        Retorna un diccionario con datos de sesión y rol, o None si no coincide.
        """
        correo = correo.strip().lower()
        with db_transaction() as cursor:
            # 1. Buscar usuario administrativo activo y obtener su rol asignado
            sql_admin = """
                SELECT u.id_usuario, u.id_sucursal, u.primer_nombre, u.primer_apellido,
                       u.correo, u.password_hash, u.activo, r.nombre_rol
                FROM USUARIOS_ADMINISTRADORES u
                JOIN ROLES_ADMIN r ON u.id_rol = r.id_rol
                WHERE LOWER(u.correo) = ? AND u.activo = 1
            """
            cursor.execute(sql_admin, (correo,))
            admin = fetch_one_dict(cursor)
            if admin:
                stored = admin["password_hash"]
                # Permite contraseñas hasheadas con PBKDF2 o texto plano inicial de pruebas
                valid = (
                    check_password(password_plano, stored)
                    if stored.startswith("pbkdf2_")
                    else (password_plano == stored)
                )
                if valid:
                    return {
                        "tipo": "admin",
                        "id": admin["id_usuario"],
                        "id_sucursal": admin["id_sucursal"],
                        "rol": admin["nombre_rol"],
                        "nombre": f"{admin['primer_nombre']} {admin['primer_apellido']}",
                        "correo": admin["correo"],
                    }

            # 2. Si no es administrador, buscar en la tabla de CLIENTES
            sql_cliente = """
                SELECT id_cliente, primer_nombre, segundo_nombre, primer_apellido,
                       segundo_apellido, correo, password_hash
                FROM CLIENTES
                WHERE LOWER(correo) = ?
            """
            cursor.execute(sql_cliente, (correo,))
            cliente = fetch_one_dict(cursor)
            if cliente:
                stored = cliente["password_hash"]
                valid = (
                    check_password(password_plano, stored)
                    if stored.startswith("pbkdf2_")
                    else (password_plano == stored)
                )
                if valid:
                    # Construye el nombre completo a partir de campos atómicos evitando espacios dobles
                    partes = [
                        cliente["primer_nombre"],
                        cliente["segundo_nombre"] or "",
                        cliente["primer_apellido"],
                        cliente["segundo_apellido"] or "",
                    ]
                    nombre_completo = " ".join(p for p in partes if p.strip())
                    return {
                        "tipo": "cliente",
                        "id": cliente["id_cliente"],
                        "id_sucursal": None,
                        "rol": "Cliente",
                        "nombre": nombre_completo,
                        "correo": cliente["correo"],
                    }

        return None

    @staticmethod
    def registrar_cliente(
        primer_nombre: str,
        segundo_nombre: str,
        primer_apellido: str,
        segundo_apellido: str,
        telefono: str,
        correo: str,
        password_plano: str,
    ):
        """
        Registra un nuevo cliente en CLIENTES almacenando nombres y apellidos de forma atómica
        y cifrando la contraseña con el algoritmo hash seguro de Django.
        """
        password_hashed = make_password(password_plano)
        with db_transaction() as cursor:
            # Verifica unicidad de correo antes de insertar
            cursor.execute(
                "SELECT id_cliente FROM CLIENTES WHERE LOWER(correo) = ?",
                (correo.strip().lower(),),
            )
            if cursor.fetchone():
                raise ValueError("Ya existe un cliente registrado con ese correo.")

            # Inserta el nuevo cliente y recupera su ID generado mediante OUTPUT INSERTED
            sql = """
                INSERT INTO CLIENTES (
                    primer_nombre, segundo_nombre, primer_apellido, segundo_apellido,
                    telefono, correo, password_hash
                )
                OUTPUT INSERTED.id_cliente
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(
                sql,
                (
                    primer_nombre.strip(),
                    segundo_nombre.strip() if segundo_nombre else None,
                    primer_apellido.strip(),
                    segundo_apellido.strip() if segundo_apellido else None,
                    telefono.strip(),
                    correo.strip().lower(),
                    password_hashed,
                ),
            )
            return cursor.fetchone()[0]