from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from equivalencias import views


class RegistroErrorEnvioTests(SimpleTestCase):
    def _correr_tarea(self, detalle, envio):
        """Ejecuta la tarea del hilo en el mismo hilo, sin tocar la base."""
        with mock.patch.object(views.threading, "Thread") as thread, \
                mock.patch.object(views.DetalleSolicitud.objects, "get", return_value=detalle), \
                mock.patch.object(views, "_enviar_email_catedra", side_effect=envio), \
                mock.patch.object(views, "connection"):
            views._enviar_email_catedra_en_segundo_plano(1)
            thread.call_args.kwargs["target"]()

    def test_si_falla_el_envio_queda_registrado_en_el_detalle(self):
        detalle = mock.MagicMock(estado_asignatura="Pendiente de envío", error_envio="")
        self._correr_tarea(detalle, TimeoutError("timed out"))

        self.assertIn("TimeoutError: timed out", detalle.error_envio)
        self.assertEqual(detalle.estado_asignatura, "Pendiente de envío")
        detalle.save.assert_called_once_with(update_fields=["error_envio"])

    def test_si_el_envio_sale_bien_marca_enviada_y_limpia_el_error(self):
        detalle = mock.MagicMock(estado_asignatura="Pendiente de envío", error_envio="viejo")
        self._correr_tarea(detalle, None)

        self.assertEqual(detalle.estado_asignatura, "Enviada a Cátedra")
        self.assertEqual(detalle.error_envio, "")
        detalle.save.assert_called_once_with(
            update_fields=["estado_asignatura", "error_envio"])


class DocumentacionGridTests(SimpleTestCase):
    def test_muestra_los_documentos_aunque_la_extension_este_en_mayuscula(self):
        from django.template.loader import render_to_string

        doc = SimpleNamespace(
            archivo=SimpleNamespace(name="private/equivalencias/perez-juan/abc.PDF"),
            fecha_subida=None,
        )
        html = render_to_string(
            "equivalencias/components/documentacion_grid.html", {"documentos": [doc]})

        self.assertIn("/file/equivalencias/perez-juan/abc.PDF", html)
        self.assertIn("bi-file-pdf", html)
        self.assertIn("Documento 1", html)
