from django.contrib import admin

from .models import HistorialDecisiones, MicrosoftToken


@admin.register(MicrosoftToken)
class MicrosoftTokenAdmin(admin.ModelAdmin):
    list_display = ("cuenta_id", "esta_vencido", "actualizado")
    readonly_fields = ("cuenta_id", "resumen_token", "creado", "actualizado")
    exclude = ("token_data",)  # nunca mostrar el JSON crudo (contiene el refresh_token)
    actions = ["revocar_token"]

    def has_add_permission(self, request):
        # El token se crea únicamente vía el flujo OAuth (iniciar_autenticacion /
        # microsoft_callback), nunca a mano desde el admin.
        return False

    @admin.display(description="Token")
    def resumen_token(self, obj):
        data = obj.token_data or {}
        scopes = data.get("scope") or data.get("scopes") or "?"
        return f"vencido={obj.esta_vencido} · scopes={scopes}"

    @admin.action(description="Revocar token seleccionado (fuerza reautenticación)")
    def revocar_token(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"{count} token(s) revocado(s).")


@admin.register(HistorialDecisiones)
class HistorialDecisionesAdmin(admin.ModelAdmin):
    list_display = (
        "correo_asunto",
        "correo_remitente",
        "categoria_ia",
        "estado",
        "fecha_recepcion",
        "fecha_decision",
    )
    list_filter = ("estado", "categoria_ia")
    search_fields = ("correo_asunto", "correo_remitente", "correo_cuerpo", "resumen_ia")
    readonly_fields = (
        "correo_message_id",
        "correo_remitente",
        "correo_asunto",
        "correo_cuerpo",
        "fecha_recepcion",
        "categoria_ia",
        "resumen_ia",
        "accion_propuesta_ia",
        "telegram_chat_id",
        "telegram_message_id",
        "fecha_creacion",
    )
