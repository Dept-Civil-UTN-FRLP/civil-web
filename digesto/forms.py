from django import forms

from .models import Acta, Certificacion, CicloLectivo, Disposicion


class CicloLectivoForm(forms.ModelForm):
    class Meta:
        model = CicloLectivo
        fields = ["anio"]
        widgets = {
            "anio": forms.NumberInput(attrs={"class": "form-control", "min": 2000, "max": 2100}),
        }
        labels = {"anio": "Año"}


class ActaForm(forms.ModelForm):
    class Meta:
        model = Acta
        fields = ["ciclo", "tipo", "numero", "mes", "contenido_md", "pdf", "referencias"]
        widgets = {
            "ciclo": forms.Select(attrs={"class": "form-select"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "numero": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "mes": forms.TextInput(attrs={"class": "form-control", "placeholder": "marzo"}),
            "contenido_md": forms.Textarea(attrs={
                "class": "form-control",
                "id": "id_contenido_md",
                "rows": 20,
            }),
            "pdf": forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdf"}),
            "referencias": forms.SelectMultiple(attrs={"class": "form-select", "size": 6}),
        }
        labels = {
            "ciclo": "Ciclo Lectivo",
            "tipo": "Tipo",
            "numero": "N° de Acta",
            "mes": "Mes",
            "contenido_md": "Contenido (Markdown)",
            "pdf": "PDF con firmas",
            "referencias": "Referencias cruzadas",
        }
        help_texts = {
            "referencias": "Mantenga Ctrl para seleccionar varias actas.",
        }


class DisposicionForm(forms.ModelForm):
    class Meta:
        model = Disposicion
        fields = ["numero", "texto", "deroga", "modifica"]
        widgets = {
            "numero": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "texto": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "deroga": forms.Select(attrs={"class": "form-select"}),
            "modifica": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "numero": "N° de disposición",
            "texto": "Texto",
            "deroga": "Deroga a",
            "modifica": "Modifica a",
        }

    def __init__(self, *args, acta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deroga"].required = False
        self.fields["modifica"].required = False
        self.fields["deroga"].empty_label = "— Ninguna —"
        self.fields["modifica"].empty_label = "— Ninguna —"
        if acta is not None:
            # Excluir disposiciones de la misma acta para evitar auto-referencia
            qs = Disposicion.objects.exclude(acta=acta).select_related("acta__ciclo")
            self.fields["deroga"].queryset = qs
            self.fields["modifica"].queryset = qs


class CertificacionForm(forms.ModelForm):
    class Meta:
        model = Certificacion
        fields = ["numero", "texto"]
        widgets = {
            "numero": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "texto": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }
        labels = {
            "numero": "N° de certificación",
            "texto": "Texto",
        }
