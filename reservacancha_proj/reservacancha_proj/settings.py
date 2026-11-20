"""
Configuración principal del proyecto Django 'reservacancha_proj'.
Las tablas de negocio residen en SQL Server y se consultan vía pyodbc;
SQLite se mantiene únicamente para la tabla interna de sesiones de Django.
"""

from pathlib import Path

# Ruta base del proyecto (carpeta donde reside manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent

# Clave secreta para firma criptográfica de sesiones y tokens CSRF (usar variable de entorno en producción)
SECRET_KEY = "django-insecure-cambia-esta-clave-en-produccion"

# Modo depuración activado para entorno de desarrollo local
DEBUG = True

ALLOWED_HOSTS = ["*"]

# Aplicaciones habilitadas: solo módulos necesarios y apps propias del dominio
INSTALLED_APPS = [
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "users",
    "reservas",
]

# Cadena de middlewares para manejo de sesiones, CSRF y mensajes flash
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "reservacancha_proj.urls"

# Configuración del motor de plantillas HTML
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "reservacancha_proj.wsgi.application"

# Base de datos interna de soporte para sesiones de Django (no contiene tablas de negocio)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "django_sessions.sqlite3",
    }
}

# Persistencia de sesión respaldada en base de datos
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Configuración regional y zona horaria
LANGUAGE_CODE = "es-hn"
TIME_ZONE = "America/Tegucigalpa"
USE_I18N = True
USE_TZ = False

# Ruta base para archivos estáticos
STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"