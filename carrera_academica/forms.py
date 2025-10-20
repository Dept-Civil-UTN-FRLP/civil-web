# carrera_academica/forms.py

from django import forms

from .models import (
    Resolucion,
    CarreraAcademica,
    Cargo,
    JuntaEvaluadora,
    Docente,
    Asignatura,
)


class ResolucionForm(forms.ModelForm):
    # Añadimos un campo que no está en el modelo para capturar la duración de la prórroga
    prorroga_dias = forms.IntegerField(
        label="Días de Prórroga",
        required=False,
        help_text="Completar solo si el objeto es 'Prorroga de Carrera Academica'.",
    )

    class Meta:
        model = Resolucion
        fields = ["objeto", "numero", "año", "origen", "file"]
        # Opcional: Añadir widgets para mejorar la apariencia
        widgets = {
            "objeto": forms.Select(attrs={"class": "form-select"}),
            "numero": forms.NumberInput(attrs={"class": "form-control"}),
            "año": forms.NumberInput(attrs={"class": "form-control"}),
            "origen": forms.Select(attrs={"class": "form-select"}),
            "file": forms.FileInput(attrs={"class": "form-control"}),
        }


class CarreraAcademicaForm(forms.ModelForm):
    """
    Formulario simplificado para iniciar una CA desde un Cargo existente.
    """

    class Meta:
        model = CarreraAcademica
        # Solo necesitamos seleccionar el cargo. Las fechas se tomarán de él.
        fields = ["cargo", "numero_expediente"]
        widgets = {
            "cargo": forms.Select(attrs={"class": "form-select"}),
            "numero_expediente": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtramos el queryset para mostrar solo cargos regulares u ordinarios que no tengan ya una CA.
        self.fields["cargo"].queryset = Cargo.objects.filter(
            carrera_academica__isnull=True, caracter__in=["reg", "ord"]
        ).select_related("docente", "asignatura")
        self.fields["cargo"].label = (
            "Seleccionar un Cargo Regular u Ordinario sin Carrera Académica iniciada"
        )


class CargoForm(forms.ModelForm):
    """
    Un formulario completo para crear un nuevo Cargo.
    """

    class Meta:
        model = Cargo
        fields = [
            "docente",
            "asignatura",
            "caracter",
            "categoria",
            "dedicacion",
            "fecha_inicio",
            "fecha_vencimiento",
        ]
        widgets = {
            "docente": forms.Select(attrs={"class": "form-select"}),
            "asignatura": forms.Select(attrs={"class": "form-select"}),
            "caracter": forms.Select(attrs={"class": "form-select"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "dedicacion": forms.Select(attrs={"class": "form-select"}),
            "fecha_inicio": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "fecha_vencimiento": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
        }


class JuntaEvaluadoraForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtramos el queryset para los campos de docentes internos
        queryset_internos = Docente.objects.filter(
            cargo_docente__caracter__in=["ord", "reg"]
        ).distinct()
        self.fields["miembro_interno_titular"].queryset = queryset_internos
        self.fields["miembro_interno_suplente"].queryset = queryset_internos

    class Meta:
        model = JuntaEvaluadora
        fields = [
            "miembro_interno_titular",
            "miembro_interno_suplente",
            "miembros_externos_titulares",
            "miembros_externos_suplentes",
            "veedor_alumno_titular",
            "veedor_alumno_suplente",
            "veedor_graduado_titular",
            "veedor_graduado_suplente",
        ]
        widgets = {
            # Usamos Select para los ForeignKey y SelectMultiple para los ManyToMany
            "miembro_interno_titular": forms.Select(attrs={"class": "form-select"}),
            "miembro_interno_suplente": forms.Select(attrs={"class": "form-select"}),
            "miembros_externos_titulares": forms.SelectMultiple(
                attrs={"class": "form-select", "size": 5}
            ),
            "miembros_externos_suplentes": forms.SelectMultiple(
                attrs={"class": "form-select", "size": 5}
            ),
            "veedor_alumno_titular": forms.Select(attrs={"class": "form-select"}),
            "veedor_alumno_suplente": forms.Select(attrs={"class": "form-select"}),
            "veedor_graduado_titular": forms.Select(attrs={"class": "form-select"}),
            "veedor_graduado_suplente": forms.Select(attrs={"class": "form-select"}),
        }


class ExpedienteForm(forms.ModelForm):
    """
    Un formulario específico para editar solo el número de expediente.
    """

    class Meta:
        model = CarreraAcademica
        fields = ["numero_expediente"]
        widgets = {
            "numero_expediente": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "placeholder": "Ej: 12345/2024",
                }
            ),
        }


class EvaluacionForm(forms.Form):
    # Este campo se llenará dinámicamente desde la vista
    anios_a_evaluar = forms.MultipleChoiceField(
        label="Seleccionar años a incluir en esta evaluación",
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )


class NotificacionJuntaForm(forms.Form):
    def __init__(self, *args, **kwargs):
        # Extraemos la junta que pasaremos desde la vista
        junta = kwargs.pop("junta")
        super().__init__(*args, **kwargs)

        # Creamos un checkbox para cada miembro de la junta
        miembros = []
        if junta.miembro_interno_titular:
            miembros.append(("docente_tit_int", junta.miembro_interno_titular))
        if junta.miembro_interno_suplente:
            miembros.append(("docente_sup_int", junta.miembro_interno_suplente))

        for i, miembro in enumerate(junta.miembros_externos_titulares.all()):
            miembros.append((f"externo_tit_{miembro.pk}", miembro))
        for i, miembro in enumerate(junta.miembros_externos_suplentes.all()):
            miembros.append((f"externo_sup_{miembro.pk}", miembro))

        for key, miembro in miembros:
            self.fields[key] = forms.BooleanField(label=str(miembro), required=False)
