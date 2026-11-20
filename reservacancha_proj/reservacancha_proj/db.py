"""
Módulo de acceso directo a SQL Server mediante pyodbc (sin ORM).
Provee gestión transaccional ACID y utilidades para mapear resultados a diccionarios.
"""

from contextlib import contextmanager
import pyodbc

# Cadena de conexión hacia SQL Server utilizando autenticación integrada de Windows.
# Si se utiliza autenticación SQL, cambiar Trusted_Connection=yes; por UID=usuario;PWD=clave;
SQLSERVER_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=DESKTOP-C64APVQ\SQLEXPRESS;"
    "DATABASE=reserva_cancha;"
    "Trusted_Connection=yes;"
)


@contextmanager
def db_transaction():
    """
    Abre una conexión a SQL Server con autocommit desactivado para garantizar
    atomicidad (ACID): confirma los cambios con commit() si todo sale bien o
    revierte todo con rollback() ante cualquier excepción.
    """
    conn = pyodbc.connect(SQLSERVER_CONN_STR)
    conn.autocommit = False
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        # Cierra siempre cursor y conexión para evitar fugas de recursos.
        cursor.close()
        conn.close()


def fetch_all_dicts(cursor):
    """
    Convierte todas las filas recuperadas por el cursor en una lista de diccionarios
    {nombre_columna: valor} para facilitar su consumo en vistas y serialización JSON.
    """
    if not cursor.description:
        return []
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def fetch_one_dict(cursor):
    """
    Convierte una única fila del cursor en un diccionario {nombre_columna: valor},
    o retorna None si no hay registros.
    """
    if not cursor.description:
        return None
    cols = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    return dict(zip(cols, row)) if row else None