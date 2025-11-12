# planta_docente/forms.py

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
            'cantidad_horas',
            'asignatura',
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
            'cantidad_horas': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': 'Ej: 20'
            }),
            'asignatura': forms.Select(attrs={
                'class': 'form-select'
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
