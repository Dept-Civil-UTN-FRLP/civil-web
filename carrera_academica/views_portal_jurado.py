# carrera_academica/views_portal_jurado.py
"""
Vistas PÚBLICAS del Portal de Jurados — reemplazan el envío de documentación
por mail con un link personal + verificación de DNI.

IMPORTANTE: estas son las ÚNICAS vistas de la app carrera_academica sin
@login_required. Están en un archivo separado de views.py a propósito, para
que quede visualmente obvio en el urls.py cuáles son las que rompen esa regla.
Su protección es una sesión propia (ver `_requiere_sesion_portal`), no la de
Django auth.
"""
import functools

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from carrera_academica.models import AccesoPortalJurado, CarreraAcademica, Formulario
from carrera_academica.services import jurado_portal_service as portal_service
from carrera_academica.services import token_portal_service
from carrera_academica.services.email_service import EmailService
from carrera_academica.services.pdf_service import PDFService

SESSION_KEY = "portal_jurado"


def _requiere_sesion_portal(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get(SESSION_KEY):
            return redirect("carrera_academica:portal_jurado_sesion_expirada")
        return view_func(request, *args, **kwargs)

    return wrapper


def _identidad_sesion(request):
    datos = request.session.get(SESSION_KEY) or {}
    return datos.get("tipo_persona"), datos.get("persona_id"), datos.get("token_id")


def _registrar_acceso(request, accion, exitoso=True, detalle="", **extra):
    tipo_persona, persona_id, token_id = _identidad_sesion(request)
    AccesoPortalJurado.objects.create(
        tipo_persona=extra.pop("tipo_persona", tipo_persona) or "",
        persona_id=extra.pop("persona_id", persona_id),
        token_id=extra.pop("token_id", token_id),
        accion=accion,
        exitoso=exitoso,
        detalle=detalle,
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        **extra,
    )


def portal_jurado_landing_view(request, token):
    """GET: formulario de DNI. POST: verifica token + DNI y abre sesión."""
    error = None

    if request.method == "POST":
        dni_ingresado = request.POST.get("dni", "").strip()
        token_obj = token_portal_service.verificar_token(token)

        if not token_obj:
            _registrar_acceso(request, "link_fail_token", exitoso=False)
            error = "Enlace inválido o expirado. Contactá a Secretaría Académica."
        else:
            persona = portal_service.resolver_persona(
                token_obj.tipo_persona, token_obj.persona_id
            )
            dni_real = portal_service.obtener_dni(persona) if persona else None

            dni_coincide = False
            if persona and dni_real is not None:
                try:
                    dni_coincide = int(dni_ingresado) == int(dni_real)
                except (TypeError, ValueError):
                    dni_coincide = False

            if not dni_coincide:
                _registrar_acceso(
                    request,
                    "link_fail_dni",
                    exitoso=False,
                    tipo_persona=token_obj.tipo_persona,
                    persona_id=token_obj.persona_id,
                    token_id=token_obj.pk,
                )
                error = "Enlace inválido o expirado. Contactá a Secretaría Académica."
            else:
                token_obj.ultimo_uso = timezone.now()
                token_obj.save(update_fields=["ultimo_uso"])

                request.session.cycle_key()
                request.session[SESSION_KEY] = {
                    "tipo_persona": token_obj.tipo_persona,
                    "persona_id": token_obj.persona_id,
                    "token_id": token_obj.pk,
                }
                request.session.set_expiry(60 * _minutos_sesion())

                _registrar_acceso(
                    request,
                    "link_ok",
                    tipo_persona=token_obj.tipo_persona,
                    persona_id=token_obj.persona_id,
                    token_id=token_obj.pk,
                )
                return redirect("carrera_academica:portal_jurado_dashboard")

    return render(
        request,
        "carrera_academica/portal_jurado/landing.html",
        {"token": token, "error": error},
    )


def _minutos_sesion():
    from django.conf import settings

    return settings.PORTAL_JURADO_SESSION_MINUTOS


def _cargo_info(ca):
    return (
        f"{ca.cargo.get_categoria_display()} {ca.cargo.get_caracter_display()} "
        f"en {ca.cargo.asignatura.nombre.title()}"
    )


@_requiere_sesion_portal
def portal_jurado_dashboard_view(request):
    tipo_persona, persona_id, _ = _identidad_sesion(request)
    persona = portal_service.resolver_persona(tipo_persona, persona_id)
    if not persona:
        return redirect("carrera_academica:portal_jurado_sesion_expirada")

    cas = portal_service.obtener_cas_para_persona(tipo_persona, persona_id)
    items = []
    for ca in cas:
        evaluacion = portal_service.obtener_evaluacion_relevante(ca)
        items.append(
            {
                "ca": ca,
                "evaluacion": evaluacion,
                "cargo_info": _cargo_info(ca),
            }
        )

    _registrar_acceso(request, "vista_dashboard")

    return render(
        request,
        "carrera_academica/portal_jurado/dashboard.html",
        {"persona": persona, "items": items},
    )


@_requiere_sesion_portal
def portal_jurado_detalle_view(request, ca_pk):
    tipo_persona, persona_id, _ = _identidad_sesion(request)

    ca_autorizadas = portal_service.obtener_cas_para_persona(
        tipo_persona, persona_id
    ).values_list("pk", flat=True)
    if ca_pk not in ca_autorizadas:
        raise Http404

    ca = get_object_or_404(CarreraAcademica, pk=ca_pk)
    evaluacion = portal_service.obtener_evaluacion_relevante(ca)
    documentos = (
        EmailService.obtener_documentos_pertinentes(ca, evaluacion.anios_evaluados)
        if evaluacion
        else []
    )

    _registrar_acceso(request, "vista_detalle_ca", carrera_academica_id=ca.pk)

    return render(
        request,
        "carrera_academica/portal_jurado/detalle.html",
        {
            "ca": ca,
            "evaluacion": evaluacion,
            "documentos": documentos,
            "cargo_info": _cargo_info(ca),
        },
    )


@_requiere_sesion_portal
def portal_jurado_documento_view(request, formulario_pk):
    tipo_persona, persona_id, _ = _identidad_sesion(request)
    formulario = get_object_or_404(Formulario, pk=formulario_pk)

    ca_autorizadas = portal_service.obtener_cas_para_persona(
        tipo_persona, persona_id
    ).values_list("pk", flat=True)
    if formulario.carrera_academica_id not in ca_autorizadas:
        raise Http404

    if not formulario.archivo:
        raise Http404

    _registrar_acceso(
        request,
        "vista_documento",
        carrera_academica_id=formulario.carrera_academica_id,
        formulario_id=formulario.pk,
    )

    if settings.DEBUG:
        # En local no hay nginx que interprete X-Accel-Redirect -- servir el
        # archivo directo para poder probar. En producción nunca entra acá.
        return FileResponse(formulario.archivo.open("rb"), content_type="application/pdf")

    # Mismo esquema que config/views_media.py::serve_private_media, pero
    # autorizando por sesión del portal en vez de @login_required.
    rel_path = formulario.archivo.name
    if rel_path.startswith("private/"):
        rel_path = rel_path[len("private/") :]

    response = HttpResponse()
    response["Content-Type"] = ""
    response["X-Accel-Redirect"] = f"/protected-media/private/{rel_path}"
    return response


@_requiere_sesion_portal
def portal_jurado_expediente_completo_view(request, ca_pk):
    tipo_persona, persona_id, _ = _identidad_sesion(request)

    ca_autorizadas = portal_service.obtener_cas_para_persona(
        tipo_persona, persona_id
    ).values_list("pk", flat=True)
    if ca_pk not in ca_autorizadas:
        raise Http404

    ca = get_object_or_404(CarreraAcademica, pk=ca_pk)
    output_buffer, errores = PDFService.consolidar_expediente(ca)

    if not output_buffer:
        # Autorizado para esta CA, pero no hay nada para consolidar -- no es
        # un caso de IDOR, así que no corresponde el 404 genérico.
        messages.info(request, "Todavía no hay documentos para consolidar en esta Carrera Académica.")
        return redirect("carrera_academica:portal_jurado_dashboard")

    _registrar_acceso(request, "descarga_expediente", carrera_academica_id=ca.pk)

    response = HttpResponse(output_buffer, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="expediente_{ca.pk}.pdf"'
    )
    return response


def portal_jurado_logout_view(request):
    request.session.pop(SESSION_KEY, None)
    return redirect("carrera_academica:portal_jurado_sesion_expirada")


def portal_jurado_sesion_expirada_view(request):
    return render(request, "carrera_academica/portal_jurado/sesion_expirada.html")
