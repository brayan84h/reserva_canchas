"""Rutas URL correspondientes al módulo de reservas, APIs y panel administrativo."""

from django.urls import path
from . import views

urlpatterns = [
    path("", views.index_view, name="index"),
    path("api/disponibilidad/", views.disponibilidad_api, name="disponibilidad_api"),
    path("reservar/", views.crear_reserva_view, name="crear_reserva"),
    path("mis-reservas/", views.mis_reservas_view, name="mis_reservas"),
    path(
        "mis-reservas/<int:id_reserva>/cancelar/",
        views.cancelar_reserva_cliente_view,
        name="cancelar_reserva_cliente",
    ),
    path(
        "mis-reservas/<int:id_reserva>/pagar/",
        views.pagar_reserva_cliente_view,
        name="pagar_reserva_cliente",
    ),
    path("panel-admin/", views.admin_panel_view, name="admin_panel"),
    path(
        "panel-admin/reservas/crear/",
        views.crear_reserva_admin_view,
        name="crear_reserva_admin",
    ),
    path(
        "panel-admin/empresas/crear/",
        views.crear_empresa_view,
        name="crear_empresa",
    ),
    path(
        "panel-admin/sucursales/crear/",
        views.crear_sucursal_view,
        name="crear_sucursal",
    ),
    path(
        "panel-admin/canchas/crear/",
        views.crear_cancha_view,
        name="crear_cancha",
    ),
    path("panel-admin/estado/", views.cambiar_estado_view, name="cambiar_estado"),
    path("panel-admin/pago/", views.registrar_pago_view, name="registrar_pago"),
    path(
        "api/auditoria/<int:id_reserva>/", views.auditoria_api, name="auditoria_api"
    ),
]