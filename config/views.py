from django.shortcuts import render


def landing_civil(request):
    perfil_items = [
        {
            "titulo": "Infraestructura urbana",
            "descripcion": "Edificios, viviendas, fábricas y toda obra relacionada con el entorno urbano.",
            "icon_path": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>',
        },
        {
            "titulo": "Vías y transporte",
            "descripcion": "Puentes, carreteras, vías ferroviarias, puertos y aeropuertos.",
            "icon_path": '<path d="M3 12h18M3 6l9-3 9 3M3 18l9 3 9-3"/>',
        },
        {
            "titulo": "Hidráulica y ambiente",
            "descripcion": "Sistemas de riego, aprovechamientos hidroeléctricos, desagües y control ecológico.",
            "icon_path": '<path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2z"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
        },
        {
            "titulo": "Gestión y planificación",
            "descripcion": "Factibilidad, presupuestación, dirección de obras y control técnico-económico.",
            "icon_path": '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
        },
    ]

    plan_estudios = [
        {"label": "1° año", "materias": ["Análisis Matemático I", "Álgebra y Geometría Analítica",
                                         "Física I", "Química General", "Sistemas de Representación"]},
        {"label": "2° año", "materias": [
            "Análisis Matemático II", "Física II", "Mecánica de los Fluidos", "Estabilidad I", "Topografía"]},
        {"label": "3° año", "materias": ["Mecánica de Suelos", "Estabilidad II",
                                         "Hormigón Armado I", "Ingeniería Sanitaria", "Vías de Comunicación"]},
        {"label": "4° y 5° año", "materias": ["Hormigón Armado II", "Estructuras Metálicas",
                                              "Hidráulica Aplicada", "Práctica Supervisada", "Proyecto Final Integrador"]},
    ]

    return render(request, "civil/landing.html", {
        "perfil_items": perfil_items,
        "plan_estudios": plan_estudios,
    })
