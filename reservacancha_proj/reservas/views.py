"""
Vistas y endpoints JSON del módulo de reservas:
catálogo público, consulta dinámica de horarios, creación y gestión de reservas
para clientes (ver estados, pagar en línea, cancelar >= 3 días) y administradores.
"""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from .repo import ReservaRepository


def _usuario_actual(request):
    return request.session.get("usuario")


def _es_super_admin(usuario):
    return bool(
        usuario
        and usuario.get("tipo") == "admin"
        and usuario.get("rol") == "Admin General"
    )


def index_view(request):
    usuario = _usuario_actual(request)
    canchas = ReservaRepository.listar_canchas_activas()
    return render(
        request,
        "reservas/index.html",
        {"canchas": canchas, "usuario": usuario},
    )


def disponibilidad_api(request):
    id_cancha = request.GET.get("id_cancha")
    fecha = request.GET.get("fecha")
    if not id_cancha or not fecha:
        return JsonResponse([], safe=False)
    horarios = ReservaRepository.obtener_horarios_disponibles(int(id_cancha), fecha)
    return JsonResponse(horarios, safe=False)


def crear_reserva_view(request):
    if request.method != "POST":
        return redirect("index")

    usuario = _usuario_actual(request)
    if not usuario or usuario.get("tipo") != "cliente":
        messages.warning(
            request, "Debes iniciar sesión como cliente para realizar una reserva."
        )
        return redirect("login")

    try:
        ReservaRepository.crear_reserva(
            id_cliente=usuario["id"],
            id_cancha=int(request.POST["id_cancha"]),
            id_horario=int(request.POST["id_horario"]),
            fecha_reserva=request.POST["fecha_reserva"],
        )
        messages.success(
            request, "Reserva registrada en estado pendiente con auditoría inicial."
        )
    except Exception as exc:
        messages.error(request, f"No se pudo completar la reserva: {exc}")

    return redirect("mis_reservas")


def mis_reservas_view(request):
    usuario = _usuario_actual(request)
    if not usuario or usuario.get("tipo") != "cliente":
        messages.warning(
            request, "Debes iniciar sesión como cliente para ver tus reservas."
        )
        return redirect("login")

    reservas = ReservaRepository.listar_reservas_cliente(usuario["id"])
    metodos = ReservaRepository.listar_metodos_pago()
    return render(
        request,
        "reservas/mis_reservas.html",
        {"usuario": usuario, "reservas": reservas, "metodos": metodos},
    )


def cancelar_reserva_cliente_view(request, id_reserva: int):
    usuario = _usuario_actual(request)
    if not usuario or usuario.get("tipo") != "cliente":
        return redirect("login")

    if request.method == "POST":
        try:
            ReservaRepository.cancelar_reserva_cliente(
                id_reserva=id_reserva,
                id_cliente=usuario["id"],
                motivo=request.POST.get(
                    "motivo", "Cancelada por el cliente con >= 3 días de anticipación"
                ),
            )
            messages.success(
                request,
                "Reserva cancelada. El horario ha quedado disponible para otra reserva.",
            )
        except Exception as exc:
            messages.error(request, str(exc))

    return redirect("mis_reservas")


def pagar_reserva_cliente_view(request, id_reserva: int):
    usuario = _usuario_actual(request)
    if not usuario or usuario.get("tipo") != "cliente":
        return redirect("login")

    if request.method == "POST":
        try:
            ReservaRepository.registrar_pago_cliente(
                id_reserva=id_reserva,
                id_cliente=usuario["id"],
                id_metodo_pago=int(request.POST["id_metodo_pago"]),
                monto=float(request.POST["monto"]),
                titular_tarjeta=request.POST.get("titular_tarjeta", ""),
                ultimos4=request.POST.get("ultimos4", ""),
                num_autorizacion=request.POST.get("numero_autorizacion", ""),
                banco_emisor=request.POST.get("banco_emisor", ""),
            )
            messages.success(request, "Pago en línea procesado correctamente.")
        except Exception as exc:
            messages.error(request, f"No se pudo procesar el pago: {exc}")

    return redirect("mis_reservas")


def admin_panel_view(request):
    usuario = _usuario_actual(request)
    if not usuario or usuario.get("tipo") != "admin":
        messages.warning(request, "Acceso restringido a usuarios administradores.")
        return redirect("login")

    es_super = _es_super_admin(usuario)
    id_sucursal = None if es_super else usuario.get("id_sucursal")

    reservas = ReservaRepository.listar_reservas_admin(id_sucursal)
    estados = ReservaRepository.listar_estados_reserva()
    metodos = ReservaRepository.listar_metodos_pago()
    clientes = ReservaRepository.listar_clientes_resumen()
    sucursales, tipos_cancha = ReservaRepository.listar_sucursales_y_tipos()
    empresas = ReservaRepository.listar_empresas() if es_super else []

    if es_super:
        canchas_gestion = ReservaRepository.listar_todas_las_canchas()
        canchas_reserva = canchas_gestion
    else:
        canchas_gestion = ReservaRepository.listar_canchas_por_sucursal(id_sucursal)
        canchas_reserva = canchas_gestion

    return render(
        request,
        "reservas/admin_panel.html",
        {
            "usuario": usuario,
            "es_super_admin": es_super,
            "reservas": reservas,
            "estados": estados,
            "metodos": metodos,
            "clientes": clientes,
            "empresas": empresas,
            "sucursales": sucursales,
            "tipos_cancha": tipos_cancha,
            "canchas_gestion": canchas_gestion,
            "canchas_reserva": canchas_reserva,
        },
    )


def crear_reserva_admin_view(request):
    usuario = _usuario_actual(request)
    if not usuario or usuario.get("tipo") != "admin":
        return redirect("login")

    if request.method == "POST":
        try:
            modo_cliente = request.POST.get("modo_cliente", "existente")
            id_cliente_existente = (
                request.POST.get("id_cliente") if modo_cliente == "existente" else None
            )
            nuevo_cliente = None
            if modo_cliente == "nuevo":
                nuevo_cliente = {
                    "primer_nombre": request.POST.get("primer_nombre", ""),
                    "segundo_nombre": request.POST.get("segundo_nombre", ""),
                    "primer_apellido": request.POST.get("primer_apellido", ""),
                    "segundo_apellido": request.POST.get("segundo_apellido", ""),
                    "telefono": request.POST.get("telefono", ""),
                    "correo": request.POST.get("correo", ""),
                    "password": request.POST.get("password", "123456"),
                }

            ReservaRepository.crear_reserva_admin(
                id_admin=usuario["id"],
                id_cancha=int(request.POST["id_cancha"]),
                id_horario=int(request.POST["id_horario"]),
                fecha_reserva=request.POST["fecha_reserva"],
                id_cliente_existente=id_cliente_existente,
                nuevo_cliente=nuevo_cliente,
            )
            messages.success(
                request, "Reserva creada correctamente desde administración."
            )
        except Exception as exc:
            messages.error(request, f"Error al crear reserva: {exc}")

    return redirect("admin_panel")


def crear_empresa_view(request):
    usuario = _usuario_actual(request)
    if not _es_super_admin(usuario):
        messages.error(request, "Solo el Super Admin puede crear empresas.")
        return redirect("admin_panel")

    if request.method == "POST":
        try:
            ReservaRepository.crear_empresa(
                nombre_fiscal=request.POST["nombre_fiscal"],
                rtn_nit=request.POST["rtn_nit"],
                correo_contacto=request.POST["correo_contacto"],
            )
            messages.success(request, "Empresa creada correctamente.")
        except Exception as exc:
            messages.error(request, f"Error al crear empresa: {exc}")

    return redirect("admin_panel")


def crear_sucursal_view(request):
    usuario = _usuario_actual(request)
    if not _es_super_admin(usuario):
        messages.error(request, "Solo el Super Admin puede crear sucursales.")
        return redirect("admin_panel")

    if request.method == "POST":
        try:
            ReservaRepository.crear_sucursal(
                id_empresa=int(request.POST["id_empresa"]),
                nombre_sucursal=request.POST["nombre_sucursal"],
                direccion=request.POST["direccion"],
                telefono=request.POST["telefono"],
            )
            messages.success(request, "Sucursal creada correctamente.")
        except Exception as exc:
            messages.error(request, f"Error al crear sucursal: {exc}")

    return redirect("admin_panel")


def crear_cancha_view(request):
    usuario = _usuario_actual(request)
    if not usuario or usuario.get("tipo") != "admin":
        return redirect("login")

    if request.method == "POST":
        try:
            es_super = _es_super_admin(usuario)
            id_sucursal = (
                int(request.POST["id_sucursal"])
                if es_super
                else int(usuario["id_sucursal"])
            )
            ReservaRepository.crear_cancha(
                id_sucursal=id_sucursal,
                id_tipo_cancha=int(request.POST["id_tipo_cancha"]),
                nombre=request.POST["nombre"],
                ubicacion_interna=request.POST.get("ubicacion_interna", ""),
                precio_hora=float(request.POST["precio_hora"]),
            )
            messages.success(request, "Cancha agregada correctamente.")
        except Exception as exc:
            messages.error(request, f"No se pudo agregar la cancha: {exc}")

    return redirect("admin_panel")


def cambiar_estado_view(request):
    usuario = _usuario_actual(request)
    if not usuario or usuario.get("tipo") != "admin":
        return redirect("login")

    if request.method == "POST":
        try:
            ReservaRepository.cambiar_estado_reserva(
                id_reserva=int(request.POST["id_reserva"]),
                id_admin=usuario["id"],
                id_estado_nuevo=int(request.POST["id_estado_nuevo"]),
                motivo=request.POST["motivo"],
            )
            messages.success(
                request, "Estado actualizado y guardado en HISTORIAL_RESERVAS."
            )
        except Exception as exc:
            messages.error(request, f"Error al cambiar estado: {exc}")

    return redirect("admin_panel")


def registrar_pago_view(request):
    usuario = _usuario_actual(request)
    if not usuario or usuario.get("tipo") != "admin":
        return redirect("login")

    if request.method == "POST":
        try:
            ReservaRepository.registrar_pago(
                id_reserva=int(request.POST["id_reserva"]),
                id_metodo_pago=int(request.POST["id_metodo_pago"]),
                id_admin=usuario["id"],
                monto=float(request.POST["monto"]),
                num_autorizacion=request.POST.get("numero_autorizacion", ""),
                banco_emisor=request.POST.get("banco_emisor", ""),
            )
            messages.success(request, "Pago registrado de forma atómica.")
        except Exception as exc:
            messages.error(request, f"Error al registrar pago: {exc}")

    return redirect("admin_panel")


def auditoria_api(request, id_reserva: int):
    historial = ReservaRepository.obtener_historial_reserva(id_reserva)
    return JsonResponse(historial, safe=False)