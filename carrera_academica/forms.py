# carrera_academica/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

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
        fields = ["cargo", "numero_expediente"]
        widgets = {
            "cargo": forms.Select(attrs={"class": "form-select"}),
            "numero_expediente": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cargo"].queryset = Cargo.objects.filter(
            carrera_academica__isnull=True, caracter__in=["reg", "ord"]
        ).select_related("docente", "asignatura")
        self.fields["cargo"].label = (
            "Seleccionar un Cargo Regular u Ordinario sin Carrera Académica iniciada"
        )

    def clean_numero_expediente(self):
        """Validar formato del número de expediente."""
        numero = self.cleaned_data.get('numero_expediente')

        if numero:
            # Formato esperado: NNNNN/AAAA (ej: 12345/2024)
            import re
            pattern = r'^\d{4,6}/\d{4}$'

            if not re.match(pattern, numero):
                raise ValidationError(
                    'El formato debe ser NNNNN/AAAA (ej: 12345/2024)',
                    code='invalid_format'
                )

            # Validar que el año sea razonable
            year = int(numero.split('/')[1])
            current_year = timezone.now().year

            if year > current_year:
                raise ValidationError(
                    f'El año no puede ser futuro. Año actual: {current_year}',
                    code='future_year'
                )

            if year < 2000:
                raise ValidationError(
                    'El año debe ser posterior a 2000',
                    code='year_too_old'
                )

        return numero


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

    def clean(self):
        """Validaciones cruzadas del formulario."""
        cleaned_data = super().clean()
        caracter = cleaned_data.get('caracter')
        fecha_vencimiento = cleaned_data.get('fecha_vencimiento')
        dedicacion = cleaned_data.get('dedicacion')

        # Validar que solo reg/ord tengan fecha de vencimiento
        if caracter not in ['reg', 'ord'] and fecha_vencimiento:
            raise ValidationError(
                'Solo los cargos Regulares u Ordinarios deben tener fecha de vencimiento.',
                code='invalid_vencimiento'
            )

        # Validar que reg/ord SÍ tengan fecha de vencimiento
        if caracter in ['reg', 'ord'] and not fecha_vencimiento:
            self.add_error(
                'fecha_vencimiento', 'Este campo es obligatorio para cargos Regulares y Ordinarios.')

        # Validar combinación caracter-dedicacion
        if caracter == 'adh' and dedicacion in ['de', 'se']:
            raise ValidationError(
                'Los cargos Ad-Honorem no pueden tener dedicación exclusiva o semi-exclusiva.',
                code='invalid_dedication'
            )

        return cleaned_data


class JuntaEvaluadoraForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

    def clean(self):
        """Validaciones cruzadas."""
        cleaned_data = super().clean()
        tit_interno = cleaned_data.get('miembro_interno_titular')
        sup_interno = cleaned_data.get('miembro_interno_suplente')

        # Validar que titular y suplente no sean la misma persona
        if tit_interno and sup_interno and tit_interno == sup_interno:
            raise ValidationError(
                'El miembro titular y suplente no pueden ser la misma persona.',
                code='duplicate_member'
            )

        # Validar que haya al menos un miembro interno
        if not tit_interno and not sup_interno:
            raise ValidationError(
                'Debe haber al menos un miembro interno (titular o suplente).',
                code='missing_internal_member'
            )

        return cleaned_data


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
    anios_a_evaluar = forms.MultipleChoiceField(
        label="Seleccionar años a incluir en esta evaluación",
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    def clean_anios_a_evaluar(self):
        """Validar que se seleccionó al menos un año."""
        anios = self.cleaned_data.get('anios_a_evaluar')

        if not anios:
            raise ValidationError(
                'Debe seleccionar al menos un año para evaluar.',
                code='no_years_selected'
            )

        # Validar que no haya años futuros
        current_year = timezone.now().year
        for anio in anios:
            if int(anio) > current_year:
                raise ValidationError(
                    f'No se puede evaluar el año futuro {anio}.',
                    code='future_year'
                )

        return anios


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
