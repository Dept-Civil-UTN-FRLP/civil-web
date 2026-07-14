"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from django.urls import include, path
from config.views import landing_civil

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from config.views import landing_civil, landing_industrial
from config.views_media import serve_private_media

LANDING_VIEWS = {
    "civil": landing_civil,
    "industrial": landing_industrial,
}

landing_view = LANDING_VIEWS.get(settings.DEPARTAMENTO)

if landing_view is None:
    raise ImproperlyConfigured(
        f"DEPARTAMENTO='{settings.DEPARTAMENTO}' no tiene una landing registrada. "
        f"Opciones válidas: {list(LANDING_VIEWS.keys())}"
    )

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", landing_view, name="landing"),
    path('file/<path:path>',
         serve_private_media, name='serve_private_media'),
]

if "equivalencias" in settings.MODULOS_ACTIVOS:
    urlpatterns += [path("equivalencia/", include("equivalencias.urls"))]

if "carrera_academica" in settings.MODULOS_ACTIVOS:
    urlpatterns += [path("carrera/", include("carrera_academica.urls"))]

if "planta_docente" in settings.MODULOS_ACTIVOS:
    urlpatterns += [path("planta/", include("planta_docente.urls"))]

if "digesto" in settings.MODULOS_ACTIVOS:
    urlpatterns += [path("digesto/", include("digesto.urls"))]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)


