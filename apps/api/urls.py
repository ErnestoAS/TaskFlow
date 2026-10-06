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
    path("pizarras/", v.pizarras, name="pizarras"),
    path("pizarras/<int:pk>/", v.pizarra, name="pizarra"),
    # Acciones explícitas (no un <str:accion> genérico, que se comería /tarjetas/, /tipos/…).
    *[
        path(f"pizarras/<int:pk>/{accion}/", v.pizarra_accion, {"accion": accion}, name=accion)
        for accion in ("archivar", "restaurar", "salir", "transferir")
    ],
    path("pizarras/<int:pk>/miembros/<int:usuario_id>/", v.miembro, name="miembro"),
    path("pizarras/<int:pk>/invitaciones/", v.invitar, name="invitar"),
    path(
        "pizarras/<int:pk>/invitaciones/<int:invitacion_id>/<str:accion>/",
        v.invitacion_accion,
        name="invitacion_accion",
    ),
    path("pizarras/<int:pk>/listas/", v.listas, name="listas"),
    path("pizarras/<int:pk>/listas/orden/", v.listas_orden, name="listas_orden"),
    path("listas/<int:pk>/", v.lista, name="lista"),
    path("pizarras/<int:pk>/tipos/", v.tipos, name="tipos"),
    path("pizarras/<int:pk>/tipos/<int:tipo_id>/", v.tipo, name="tipo"),
    path("pizarras/<int:pk>/tarjetas/", v.tarjetas, name="tarjetas"),
    path("tarjetas/<int:pk>/", v.tarjeta, name="tarjeta"),
    path("tarjetas/<int:pk>/mover/", v.tarjeta_mover, name="tarjeta_mover"),
    path("tarjetas/<int:pk>/checklist/", v.checklist, name="checklist"),
    path("tarjetas/<int:pk>/checklist/orden/", v.checklist_orden, name="checklist_orden"),
    path("checklist/<int:pk>/", v.elemento, name="elemento"),
    path("checklist/<int:pk>/convertir/", v.elemento_convertir, name="elemento_convertir"),
    path("invitaciones/<str:token>/", v.invitacion_publica, name="invitacion"),
    path("invitaciones/<str:token>/aceptar/", v.aceptar_invitacion, name="aceptar_invitacion"),
    path(
        "invitaciones/<str:token>/registro/",
        v.registro_por_invitacion,
        name="registro_por_invitacion",
    ),
]
