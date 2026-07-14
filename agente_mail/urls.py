from django.urls import path

from . import views

app_name = "agente_mail"

urlpatterns = [
    path("microsoft/iniciar/", views.iniciar_autenticacion, name="iniciar_autenticacion"),
    path("microsoft/callback/", views.microsoft_callback, name="microsoft_callback"),
]
