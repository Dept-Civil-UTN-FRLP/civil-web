# planta_docente/forms.py

from planta_docente.models import PlanificacionAnual
from django.core.exceptions import ValidationError
from django import forms
from .models import Cargo, Docente, Asignatura
from django.utils import timezone


class CargoForm(forms.ModelForm):
    """Formulario para crear y editar cargos docentes."""

    class Meta:
        model = Cargo
        fields = [
            'docente',
            'caracter',
            'categoria',
            'dedicacion',
            'cantidad_dedicaciones',
            'cantidad_horas',
            'asignatura',
            'cantidad_comisiones',
            'fecha_inicio',
            'fecha_vencimiento',
            'estado',
        ]
        widgets = {
            'docente': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'caracter': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'categoria': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'dedicacion': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'cantidad_dedicaciones': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '5',
                'value': 1,
            }),
            'cantidad_horas': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': 'Ej: 20'
            }),
            'asignatura': forms.Select(attrs={
                'class': 'form-select'
            }),
            'cantidad_comisiones': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'value': 1,
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'fecha_vencimiento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Ordenar docentes por apellido (solo no jubilados)
        self.fields['docente'].queryset = Docente.objects.filter(
            jubilado=False
        ).order_by('apellido', 'nombre')

        # Ordenar asignaturas por nombre
        self.fields['asignatura'].queryset = Asignatura.objects.all().order_by(
            'nombre')
        self.fields['asignatura'].required = False

        # Cantidad de horas opcional
        self.fields['cantidad_horas'].required = False

        # Estado por defecto: Activo (solo para nuevos)
        if not self.instance.pk:
            self.fields['estado'].initial = 'activo'

        # Labels mejorados
        self.fields['docente'].label = 'Docente'
        self.fields['caracter'].label = 'Carácter del Cargo'
        self.fields['categoria'].label = 'Categoría'
        self.fields['dedicacion'].label = 'Dedicación'
        self.fields['cantidad_dedicaciones'].label = 'Cantidad de Dedicaciones'
        self.fields['cantidad_horas'].label = 'Cantidad de Horas (opcional)'
        self.fields['asignatura'].label = 'Asignatura (opcional)'
        self.fields['fecha_inicio'].label = 'Fecha de Inicio'
        self.fields['fecha_vencimiento'].label = 'Fecha de Vencimiento'
        self.fields['estado'].label = 'Estado'

    def clean(self):
        """Validaciones personalizadas."""
        cleaned_data = super().clean()
        caracter = cleaned_data.get('caracter')
        categoria = cleaned_data.get('categoria')
        fecha_vencimiento = cleaned_data.get('fecha_vencimiento')
        fecha_inicio = cleaned_data.get('fecha_inicio')

        # Validación 1: Interinos y Ad-Honorem deben tener fecha de vencimiento
        if caracter in ['interino', 'ad-honorem']:
            if not fecha_vencimiento:
                self.add_error('fecha_vencimiento',
                               'Los cargos interinos y ad-honorem deben tener fecha de vencimiento')

        # Validación 2: Titular solo puede ser Regular u Ordinario
        if categoria == 'titular' and caracter not in ['regular', 'ordinario']:
            self.add_error('caracter',
                           'Los cargos de categoría Titular deben ser Regular u Ordinario (no Interino ni Ad-Honorem)')

        # Validación 3: Fecha de vencimiento debe ser posterior a fecha de inicio
        if fecha_inicio and fecha_vencimiento:
            if fecha_vencimiento <= fecha_inicio:
                self.add_error('fecha_vencimiento',
                               'La fecha de vencimiento debe ser posterior a la fecha de inicio')

        return cleaned_data


class AsignaturaFichaForm(forms.ModelForm):
    """
    Formulario para editar la ficha completa de una asignatura.
    Incluye datos académicos y administrativos.
    """

    class Meta:
        model = Asignatura
        fields = [
            'nombre',
            'numero_orden',
            'nivel',
            'departamento',
            'especialidad',
            'dictado',
            'obligatoria',
            'hora_semanal',
            'hora_total',
            'numero_comisiones',
            'numero_estudiantes',
            'competencias',
            'objetivos',
            'contenidos_minimos',
            'bibliografia_basica',
            'bibliografia_complementaria',
        ]

        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Resistencia de Materiales'
            }),
            'numero_orden': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 16'
            }),
            'nivel': forms.Select(attrs={'class': 'form-select'}),
            'departamento': forms.Select(attrs={'class': 'form-select'}),
            'especialidad': forms.Select(attrs={'class': 'form-select'}),
            'dictado': forms.Select(attrs={'class': 'form-select'}),
            'obligatoria': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'hora_semanal': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 4'
            }),
            'hora_total': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 96'
            }),
            'numero_comisiones': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 2'
            }),
            'numero_estudiantes': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 80'
            }),
            'competencias': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: CE01-CE03-CE08-CE17-CE19'
            }),
            'objetivos': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Un objetivo por línea:\n• Conocer los conceptos...\n• Calcular tensiones...'
            }),
            'contenidos_minimos': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Contenidos mínimos de la asignatura...'
            }),
            'bibliografia_basica': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': '[1] A. Autor, "Título", Editorial, Año.\n[2] A. Autor y B. Autor, "Título", Editorial, Año.',
            }),
            'bibliografia_complementaria': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': '[1] A. Autor, "Título", Editorial, Año.',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Labels personalizados
        self.fields['numero_orden'].label = "Nº de Orden"
        self.fields['hora_semanal'].label = "Horas Cátedra Semanales"
        self.fields['hora_total'].label = "Horas Reloj Total"
        self.fields['numero_comisiones'].label = "Cantidad de Comisiones"
        self.fields['numero_estudiantes'].label = "Cantidad Promedio de Estudiantes"
        self.fields['bibliografia_basica'].label = "Bibliografía Básica"
        self.fields['bibliografia_complementaria'].label = "Bibliografía Complementaria"
        self.fields['bibliografia_basica'].help_text = "Formato IEEE, un ítem por línea."
        self.fields['bibliografia_complementaria'].help_text = "Formato IEEE, un ítem por línea."


class PlanificacionUploadForm(forms.ModelForm):
    """
    Formulario para subir archivos de planificación.
    """

    class Meta:
        model = PlanificacionAnual
        fields = ['archivo', 'observaciones']
        widgets = {
            'archivo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.docx',
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones adicionales (opcional)'
            }),
        }
        labels = {
            'archivo': 'Archivo de Planificación',
            'observaciones': 'Observaciones',
        }
        help_texts = {
            'archivo': 'Formatos permitidos: PDF, DOCX. Tamaño máximo: 20MB',
        }


class NotificacionForm(forms.Form):
    """
    Formulario para configurar notificaciones.
    """
    TIPO_CHOICES = [
        ('generico', 'Mensaje genérico'),
        ('personalizado', 'Mensaje personalizado'),
    ]

    tipo_mensaje = forms.ChoiceField(
        choices=TIPO_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='generico',
        label='Tipo de mensaje'
    )

    adjuntar_ficha = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Adjuntar ficha de asignatura'
    )

    cuerpo_personalizado = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 8,
            'placeholder': 'Escriba aquí el mensaje personalizado...'
        }),
        label='Mensaje personalizado'
    )

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo_mensaje')
        cuerpo = cleaned_data.get('cuerpo_personalizado')

        if tipo == 'personalizado' and not cuerpo:
            raise ValidationError(
                'Debe escribir un mensaje personalizado si selecciona esta opción.'
            )

        return cleaned_data
