from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Placeholder — implementación real en el paso 07 del plan (issues/agente_mail/07_comando_revisar_mails.md)."

    def handle(self, *args, **options):
        raise NotImplementedError(
            "revisar_mails todavía no está implementado (paso 07 del plan)."
        )
