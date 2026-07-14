from django.db import models
from django.utils import timezone


class MicrosoftToken(models.Model):
    """Token OAuth2 de Microsoft Graph (permisos delegados) para una casilla institucional.

    Guardado como JSON crudo (tal como lo entrega la librería O365 / MSAL) para que
    DjangoTokenBackend (ver 03_token_backend_o365.md) pueda leerlo y sobreescribirlo sin
    tener que mapear cada campo del token a una columna.
    """

    cuenta_id = models.CharField(
        max_length=50,
        unique=True,
        default="principal",
        help_text="Identificador de la casilla. Una sola cuenta institucional por ahora.",
    )
    token_data = models.JSONField()
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Token de Microsoft"
        verbose_name_plural = "Tokens de Microsoft"

    def __str__(self):
        return f"MicrosoftToken({self.cuenta_id})"

    @property
    def expira_en(self):
        """Timestamp unix de expiración del access_token, si está presente en el JSON."""
        return self.token_data.get("expires_at")

    @property
    def esta_vencido(self):
        expira_en = self.expira_en
        if not expira_en:
            return True
        return timezone.now().timestamp() >= expira_en


class HistorialDecisiones(models.Model):
    """Un correo procesado por el agente, la propuesta del LLM y la decisión humana.

    Cada fila es también un ejemplo para few-shot prompting dinámico: la combinación de
    (asunto, cuerpo, categoria_ia, accion_propuesta_ia, estado, texto_final) de las últimas N
    decisiones ya tomadas se usa como contexto para el LLM en corridas futuras.
    """

    ESTADO_PENDIENTE = "pendiente"
    ESTADO_ESPERANDO_TEXTO = "esperando_texto"
    ESTADO_APROBADO = "aprobado"
    ESTADO_MODIFICADO = "modificado"
    ESTADO_DESCARTADO = "descartado"
    ESTADO_ENVIADO = "enviado"
    ESTADO_ERROR = "error"

    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente de revisión"),
        (ESTADO_ESPERANDO_TEXTO, "Esperando texto modificado"),
        (ESTADO_APROBADO, "Aprobado"),
        (ESTADO_MODIFICADO, "Modificado"),
        (ESTADO_DESCARTADO, "Descartado"),
        (ESTADO_ENVIADO, "Acción ejecutada"),
        (ESTADO_ERROR, "Error al ejecutar"),
    ]

    # Identificación del correo en O365 (evita reprocesar el mismo mensaje si el cron
    # corre de nuevo antes de que se marque como leído, o si el comando se interrumpe).
    correo_message_id = models.CharField(max_length=255, unique=True, db_index=True)
    correo_remitente = models.EmailField()
    correo_asunto = models.CharField(max_length=500)
    correo_cuerpo = models.TextField()
    fecha_recepcion = models.DateTimeField()

    # Salida del LLM
    categoria_ia = models.CharField(max_length=100, blank=True)
    resumen_ia = models.TextField(blank=True)
    accion_propuesta_ia = models.TextField(
        blank=True, help_text="Borrador de respuesta o acción sugerida por el LLM."
    )

    # Decisión humana
    estado = models.CharField(
        max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE, db_index=True
    )
    texto_final = models.TextField(
        blank=True,
        help_text="Texto realmente enviado: igual a accion_propuesta_ia si fue 'aprobado', "
        "editado por el admin si fue 'modificado'.",
    )
    decidido_por_telegram_id = models.BigIntegerField(null=True, blank=True)
    fecha_decision = models.DateTimeField(null=True, blank=True)
    notas = models.TextField(blank=True)

    # Trazabilidad del mensaje de Telegram (para poder editarlo tras la decisión en vez de
    # spamear un mensaje nuevo por cada click).
    telegram_chat_id = models.BigIntegerField(null=True, blank=True)
    telegram_message_id = models.BigIntegerField(null=True, blank=True)
    # message_id del mensaje "Escribí el texto final para..." (ForceReply). Permite matchear
    # la respuesta de texto del admin contra ESTA decisión puntual y no otra que también esté
    # en estado ESPERANDO_TEXTO al mismo tiempo (ver 06_webhook_telegram.md).
    telegram_prompt_message_id = models.BigIntegerField(null=True, blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_recepcion", "-id"]
        verbose_name = "Decisión sobre correo"
        verbose_name_plural = "Historial de Decisiones"

    def __str__(self):
        return f"[{self.get_estado_display()}] {self.correo_asunto}"

    def marcar_esperando_texto(self):
        self.estado = self.ESTADO_ESPERANDO_TEXTO
        self.save(update_fields=["estado"])

    def decidir(self, telegram_user_id, nuevo_estado, texto_final=None, notas=None):
        """Aplica la decisión tomada desde Telegram. No ejecuta la acción en el correo:
        eso lo hace la vista del webhook o el comando, después de llamar a este método,
        porque requiere el Account de O365 (ver 06_webhook_telegram.md)."""
        estados_validos = {
            self.ESTADO_APROBADO,
            self.ESTADO_MODIFICADO,
            self.ESTADO_DESCARTADO,
        }
        if nuevo_estado not in estados_validos:
            raise ValueError(f"Estado inválido para decidir(): {nuevo_estado!r}")

        self.estado = nuevo_estado
        self.decidido_por_telegram_id = telegram_user_id
        self.fecha_decision = timezone.now()
        if texto_final is not None:
            self.texto_final = texto_final
        elif nuevo_estado == self.ESTADO_APROBADO:
            self.texto_final = self.accion_propuesta_ia
        if notas:
            self.notas = notas
        self.save()

    def marcar_enviado(self):
        self.estado = self.ESTADO_ENVIADO
        self.save(update_fields=["estado"])

    def marcar_error(self, mensaje):
        self.estado = self.ESTADO_ERROR
        self.notas = (self.notas + "\n" if self.notas else "") + f"Error: {mensaje}"
        self.save(update_fields=["estado", "notas"])

    @classmethod
    def ejemplos_para_few_shot(cls, limite=5):
        """Últimas decisiones ya tomadas (no pendientes), para usar como ejemplos en el
        prompt del LLM. Ver 07_comando_revisar_mails.md / llm_service.py."""
        return list(
            cls.objects.exclude(
                estado__in=[cls.ESTADO_PENDIENTE, cls.ESTADO_ESPERANDO_TEXTO]
            )
            .order_by("-fecha_decision")[:limite]
        )
