from django.urls import path

from . import vistas as v

app_name = "api"

urlpatterns = [
    path("auth/csrf/", v.csrf, name="csrf"),
    path("auth/entrar/", v.entrar, name="entrar"),
    path("auth/salir/", v.salir, name="salir"),
    path("auth/registro/", v.registro, name="registro"),
    path("auth/verificar/", v.verificar, name="verificar"),
    path("auth/verificar/reenviar/", v.reenviar_verificacion, name="reenviar_verificacion"),
    path("auth/recuperar/", v.recuperar, name="recuperar"),
    path("auth/recuperar/confirmar/", v.recuperar_confirmar, name="recuperar_confirmar"),
    path("yo/", v.yo, name="yo"),
    path("yo/password/", v.cambiar_password, name="cambiar_password"),
    path("yo/tarjetas/", v.mis_tarjetas, name="mis_tarjetas"),
    path("proyectos/", v.proyectos, name="proyectos"),
    path("proyectos/<int:pk>/", v.proyecto, name="proyecto"),
    # Acciones explícitas (no un <str:accion> genérico, que se comería /tarjetas/, /tipos/…).
    *[
        path(f"proyectos/<int:pk>/{accion}/", v.proyecto_accion, {"accion": accion}, name=accion)
        for accion in ("archivar", "restaurar", "salir", "transferir")
    ],
    path("proyectos/<int:pk>/miembros/<int:usuario_id>/", v.miembro, name="miembro"),
    path("proyectos/<int:pk>/invitaciones/", v.invitar, name="invitar"),
    path(
        "proyectos/<int:pk>/invitaciones/<int:invitacion_id>/<str:accion>/",
        v.invitacion_accion,
        name="invitacion_accion",
    ),
    path("proyectos/<int:pk>/tipos/", v.tipos, name="tipos"),
    path("proyectos/<int:pk>/tipos/<int:tipo_id>/", v.tipo, name="tipo"),
    path("proyectos/<int:pk>/tarjetas/", v.tarjetas, name="tarjetas"),
    path("tarjetas/<int:pk>/", v.tarjeta, name="tarjeta"),
    path("tarjetas/<int:pk>/estatus/", v.tarjeta_estatus, name="tarjeta_estatus"),
    path("invitaciones/<str:token>/", v.invitacion_publica, name="invitacion"),
    path("invitaciones/<str:token>/aceptar/", v.aceptar_invitacion, name="aceptar_invitacion"),
    path(
        "invitaciones/<str:token>/registro/",
        v.registro_por_invitacion,
        name="registro_por_invitacion",
    ),
]
