# config/pagination.py
"""
Clases de paginación personalizadas para el proyecto.
"""
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.conf import settings


class CustomPaginator:
    """Paginador personalizado con configuración por defecto."""

    # Configuración por defecto
    DEFAULT_PAGE_SIZE = 25
    MAX_PAGE_SIZE = 100
    PAGE_SIZE_OPTIONS = [10, 25, 50, 100]

    def __init__(self, queryset, request, page_size=None):
        """
        Inicializa el paginador.
        
        Args:
            queryset: QuerySet de Django
            request: HttpRequest object
            page_size: Tamaño de página (opcional)
        """
        self.queryset = queryset
        self.request = request

        # Obtener tamaño de página de la query string o usar default
        self.page_size = self._get_page_size(page_size)

        # Obtener número de página
        self.page_number = self._get_page_number()

        # Crear paginador
        self.paginator = Paginator(queryset, self.page_size)

        # Obtener página actual
        self.page_obj = self._get_page_obj()

    def _get_page_size(self, page_size):
        """Obtiene el tamaño de página validado."""
        # Prioridad: parámetro > query string > default
        if page_size:
            return min(page_size, self.MAX_PAGE_SIZE)

        try:
            size = int(self.request.GET.get(
                'page_size', self.DEFAULT_PAGE_SIZE))
            return min(max(size, 1), self.MAX_PAGE_SIZE)
        except (ValueError, TypeError):
            return self.DEFAULT_PAGE_SIZE

    def _get_page_number(self):
        """Obtiene el número de página."""
        return self.request.GET.get('page', 1)

    def _get_page_obj(self):
        """Obtiene el objeto de página."""
        try:
            return self.paginator.page(self.page_number)
        except PageNotAnInteger:
            return self.paginator.page(1)
        except EmptyPage:
            return self.paginator.page(self.paginator.num_pages)

    def get_context(self):
        """Retorna el contexto para el template."""
        return {
            'page_obj': self.page_obj,
            'paginator': self.paginator,
            'page_size': self.page_size,
            'page_size_options': self.PAGE_SIZE_OPTIONS,
            'is_paginated': self.paginator.num_pages > 1,
            'total_count': self.paginator.count,
        }

    def get_page_range(self, on_each_side=3, on_ends=2):
        """
        Retorna un rango de páginas optimizado para mostrar.
        Similar a get_elided_page_range de Django 3.2+
        """
        page_number = self.page_obj.number
        num_pages = self.paginator.num_pages

        # Si hay pocas páginas, mostrar todas
        if num_pages <= (on_each_side * 2 + on_ends * 2 + 1):
            return range(1, num_pages + 1)

        # Construir rango con elipsis
        page_range = []

        # Páginas del inicio
        for i in range(1, min(on_ends + 1, num_pages + 1)):
            page_range.append(i)

        # Primera elipsis si es necesario
        if page_number > (on_each_side + on_ends + 1):
            page_range.append(None)  # None representa "..."

        # Páginas alrededor de la actual
        start = max(on_ends + 1, page_number - on_each_side)
        end = min(num_pages - on_ends, page_number + on_each_side)

        for i in range(start, end + 1):
            if i not in page_range:
                page_range.append(i)

        # Segunda elipsis si es necesario
        if page_number < (num_pages - on_each_side - on_ends):
            page_range.append(None)

        # Páginas del final
        for i in range(max(num_pages - on_ends + 1, on_ends + 1), num_pages + 1):
            if i not in page_range:
                page_range.append(i)

        return page_range


def paginate_queryset(queryset, request, page_size=None):
    """
    Función helper para paginar un queryset.
    
    Args:
        queryset: QuerySet a paginar
        request: HttpRequest
        page_size: Tamaño de página opcional
    
    Returns:
        tuple: (page_obj, context_dict)
    """
    paginator = CustomPaginator(queryset, request, page_size)
    return paginator.page_obj, paginator.get_context()
