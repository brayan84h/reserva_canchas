"""
Controladores/vistas HTTP para gestión de sesión de usuarios:
inicio de sesión (login), registro de clientes y cierre de sesión (logout).
"""

from django.contrib import messages
from django.shortcuts import redirect, render
from .repo import UserRepository


def login_view(request):
    """Procesa el formulario de login y redirige según el tipo de usuario (admin o cliente)."""
    if request.method == "POST":
        correo = request.POST.get("correo", "")
        password = request.POST.get("password", "")
        usuario = UserRepository.autenticar_usuario(correo, password)
        if usuario:
            # Guarda el perfil autenticado en la sesión de Django
            request.session["usuario"] = usuario
            messages.success(request, f"Bienvenido/a, {usuario['nombre']}.")
            if usuario["tipo"] == "admin":
                return redirect("admin_panel")
            return redirect("index")
        messages.error(request, "Correo o contraseña incorrectos.")

    return render(request, "users/login.html")


def register_view(request):
    """Procesa el registro de un nuevo cliente con campos atómicos."""
    if request.method == "POST":
        try:
            UserRepository.registrar_cliente(
                primer_nombre=request.POST.get("primer_nombre", ""),
                segundo_nombre=request.POST.get("segundo_nombre", ""),
                primer_apellido=request.POST.get("primer_apellido", ""),
                segundo_apellido=request.POST.get("segundo_apellido", ""),
                telefono=request.POST.get("telefono", ""),
                correo=request.POST.get("correo", ""),
                password_plano=request.POST.get("password", ""),
            )
            messages.success(
                request, "Registro completado. Ahora puedes iniciar sesión."
            )
            return redirect("login")
        except Exception as exc:
            messages.error(request, str(exc))

    return render(request, "users/register.html")


def logout_view(request):
    """Limpia por completo la sesión activa y redirige al login."""
    request.session.flush()
    messages.info(request, "Sesión cerrada.")
    return redirect("login")