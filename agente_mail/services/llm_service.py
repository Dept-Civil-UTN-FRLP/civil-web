# Centinela que el LLM usa cuando un correo no necesita respuesta. telegram_webhook (paso 06)
# importa esta misma constante para saber cuándo "Aprobar" debe solo marcar como leído en vez
# de mandar una respuesta real — no cambies este string sin actualizar también 06_webhook_telegram.md.
SIN_RESPUESTA_NECESARIA = "(no requiere respuesta)"

# Resto de la implementación (PROMPT_SISTEMA, AnalisisCorreo, analizar_correo) se agrega en el
# paso 07 (issues/agente_mail/07_comando_revisar_mails.md).
