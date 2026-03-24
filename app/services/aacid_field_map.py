"""Mapeo de campos del PDF Anexo II A ↔ datos del proyecto."""

# Mapeo campo PDF (patron parcial) → configuracion de origen de datos
FIELD_MAP = {
    # =====================================================
    # PAGINA 1 — Datos generales
    # =====================================================

    # Convocatoria
    "CABECERA[0].CONVOCATORIA-EJERCICIO[0].CAMPO-RELLENABLE[0]": {
        "source": "project.convocatoria",
        "label": "Convocatoria",
        "max_chars": None,
    },

    # Titulo (1.1)
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.1[0].NOMBRE[0]": {
        "source": "project.titulo",
        "label": "Titulo del proyecto (1.1)",
        "max_chars": None,
    },

    # Localizacion (1.2)
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.2[0].LINEA[0].NOMBRE[0]": {
        "source": "project.pais",
        "label": "Pais (1.2)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.2[0].LINEA[0].NOMBRE[2]": {
        "source": "project.municipios",
        "label": "Municipios (1.2)",
        "max_chars": None,
    },

    # Sector CRS y Metas ODS (1.3)
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.3[0].LINEA[0].NOMBRE[0]": {
        "source": "project.crs_sector_1",
        "label": "Sector CRS 1 (1.3)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.3[0].LINEA[0].NOMBRE[1]": {
        "source": "project.ods_meta_1",
        "label": "Meta ODS 1 (1.3)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.3[0].LINEA[1].NOMBRE[0]": {
        "source": "project.crs_sector_2",
        "label": "Sector CRS 2 (1.3)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.3[0].LINEA[1].NOMBRE[1]": {
        "source": "project.ods_meta_2",
        "label": "Meta ODS 2 (1.3)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.3[0].LINEA[2].NOMBRE[0]": {
        "source": "project.crs_sector_3",
        "label": "Sector CRS 3 (1.3)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.3[0].LINEA[2].NOMBRE[1]": {
        "source": "project.ods_meta_3",
        "label": "Meta ODS 3 (1.3)",
        "max_chars": None,
    },

    # =====================================================
    # PAGINA 2 — Voluntariado, poblacion, descripcion
    # =====================================================

    # Voluntariado (1.4)
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.4[0].NOMBRE-APELLIDOS-RAZON[0]": {
        "source": "volunteers.women",
        "label": "Voluntarias mujeres (1.4)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.4[0].NOMBRE-APELLIDOS-RAZON[1]": {
        "source": "volunteers.men",
        "label": "Voluntarios hombres (1.4)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.4[0].NOMBRE-APELLIDOS-RAZON[2]": {
        "source": "volunteers.total",
        "label": "Voluntarios total (1.4)",
        "max_chars": None,
    },

    # Poblacion destinataria (1.5)
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.5[0].NOMBRE-APELLIDOS-RAZON[0]": {
        "source": "beneficiaries.women_direct",
        "label": "Beneficiarias mujeres (1.5)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.5[0].NOMBRE-APELLIDOS-RAZON[1]": {
        "source": "beneficiaries.men_direct",
        "label": "Beneficiarios hombres (1.5)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.5[0].NOMBRE-APELLIDOS-RAZON[2]": {
        "source": "beneficiaries.total_direct",
        "label": "Beneficiarios total (1.5)",
        "max_chars": None,
    },

    # Periodo de ejecucion (1.6)
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.6[0].NOMBRE-APELLIDOS-RAZON[0]": {
        "source": "project.duracion_meses",
        "label": "Duracion en meses (1.6)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.6[0].NOMBRE-APELLIDOS-RAZON[1]": {
        "source": "project.fecha_inicio",
        "label": "Fecha inicio (1.6)",
        "max_chars": None,
    },
    "APARTADO-1[0].CUERPO[0].CAJA-1\\.6[0].NOMBRE-APELLIDOS-RAZON[2]": {
        "source": "project.fecha_finalizacion",
        "label": "Fecha fin (1.6)",
        "max_chars": None,
    },

    # Descripcion del proyecto (1.7) — max 1000 chars
    "CAJA-1\\.7[0].SUBCABECERA[0].CAMPO-RELLENABLE[0]": {
        "source": "project.descripcion_breve",
        "label": "Descripcion breve (1.7)",
        "max_chars": 1000,
    },

    # =====================================================
    # SECCIONES NARRATIVAS (2.1 a 2.5) — max 4000 chars cada una
    # =====================================================

    # 2.1 Antecedentes, contexto y justificacion
    "CAJA-2\\.1[0].LINEA[1].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.1.1",
        "label": "Antecedentes y contexto (2.1.1)",
        "max_chars": 4000,
    },
    "CAJA-2\\.1[0].LINEA[2].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.1.2",
        "label": "Problemas e intereses (2.1.2)",
        "max_chars": 4000,
    },
    "CAJA-2\\.1[0].LINEA[3].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.1.3",
        "label": "Apropiacion y alineamiento (2.1.3)",
        "max_chars": 4000,
    },

    # 2.2 Analisis de actores
    "CAJA-2\\.2[0].LINEA[1].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.2.1",
        "label": "Poblacion destinataria (2.2.1)",
        "max_chars": 4000,
    },
    "CAJA-2\\.2[0].LINEA[2].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.2.2",
        "label": "Contraparte (2.2.2)",
        "max_chars": 4000,
    },
    "CAJA-2\\.2[0].LINEA[3].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.2.3",
        "label": "Entidad solicitante (2.2.3)",
        "max_chars": 4000,
    },
    "CAJA-2\\.2[0].LINEA[4].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.2.4",
        "label": "Otras organizaciones (2.2.4)",
        "max_chars": 4000,
    },
    "CAJA-2\\.2[0].LINEA[5].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.2.5",
        "label": "Personal voluntario (2.2.5)",
        "max_chars": 4000,
    },

    # 2.3.3 Metodologia y 2.3.4 Plan de trabajo
    "CAJA-2\\.3\\.3[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.3.3",
        "label": "Metodologia (2.3.3)",
        "max_chars": 4000,
    },
    "CAJA-2\\.3\\.3[1].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.3.4",
        "label": "Plan de trabajo (2.3.4)",
        "max_chars": 4000,
    },

    # 2.4 Otros aspectos
    "APARTADO-2-CONT[0].CAJA-2\\.4[0].CUERPO[0].LINEA[0].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.4.1",
        "label": "Viabilidad (2.4.1)",
        "max_chars": 4000,
    },
    "APARTADO-2-CONT[0].CAJA-2\\.4[0].CUERPO[0].LINEA[1].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.4.2",
        "label": "Sostenibilidad (2.4.2)",
        "max_chars": 4000,
    },
    "APARTADO-2-CONT[0].CAJA-2\\.4[0].CUERPO[0].LINEA[2].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.4.3",
        "label": "Impacto esperado (2.4.3)",
        "max_chars": 4000,
    },
    "APARTADO-2-CONT[0].CAJA-2\\.4[0].CUERPO[0].LINEA[3].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.4.4",
        "label": "Hipotesis y riesgos (2.4.4)",
        "max_chars": 4000,
    },

    # 2.5 Enfoques transversales PACODE
    "APARTADO-2-CONT[0].CAJA-2\\.4[1].CUERPO[0].LINEA[0].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.5.1",
        "label": "DDHH (2.5.1)",
        "max_chars": 4000,
    },
    "APARTADO-2-CONT[0].CAJA-2\\.4[1].CUERPO[0].LINEA[1].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.5.2",
        "label": "Genero (2.5.2)",
        "max_chars": 4000,
    },
    "APARTADO-2-CONT[0].CAJA-2\\.4[1].CUERPO[0].LINEA[2].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.5.3",
        "label": "Infancia (2.5.3)",
        "max_chars": 4000,
    },
    "APARTADO-2-CONT[0].CAJA-2\\.4[1].CUERPO[0].LINEA[3].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.5.4",
        "label": "Fortalecimiento democratico (2.5.4)",
        "max_chars": 4000,
    },
    "APARTADO-2-CONT[0].CAJA-2\\.4[1].CUERPO[0].LINEA[4].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.5.5",
        "label": "Territorial multiactor (2.5.5)",
        "max_chars": 4000,
    },
    "APARTADO-2-CONT[0].CAJA-2\\.4[1].CUERPO[0].LINEA[5].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.5.6",
        "label": "Accion por el clima (2.5.6)",
        "max_chars": 4000,
    },
    "APARTADO-2-CONT[0].CAJA-2\\.4[1].CUERPO[0].LINEA[6].CUERPO[0].CAMPO-RELLENABLE[0]": {
        "source": "narrative:2.5.7",
        "label": "Diversidad cultural (2.5.7)",
        "max_chars": 4000,
    },
}

NARRATIVE_SECTIONS = {
    "2.1.1": "Antecedentes y contexto",
    "2.1.2": "Problemas e intereses identificados",
    "2.1.3": "Apropiacion, alineamiento, complementariedad y armonizacion",
    "2.2.1": "Poblacion destinataria",
    "2.2.2": "Contraparte (experiencia y capacidad de gestion)",
    "2.2.3": "Entidad solicitante (experiencia y capacidad de gestion)",
    "2.2.4": "Otras organizaciones con participacion significativa",
    "2.2.5": "Personal voluntario",
    "2.3.3": "Metodologia de ejecucion",
    "2.3.4": "Plan de trabajo",
    "2.4.1": "Viabilidad",
    "2.4.2": "Sostenibilidad",
    "2.4.3": "Impacto esperado y elementos innovadores",
    "2.4.4": "Hipotesis y riesgos",
    "2.5.1": "Enfoque basado en derechos humanos",
    "2.5.2": "Enfoque de genero y feminista",
    "2.5.3": "Enfoque basado en derechos de infancia y adolescencia",
    "2.5.4": "Enfoque de fortalecimiento democratico y dialogo social",
    "2.5.5": "Enfoque territorial multiactor",
    "2.5.6": "Enfoque de accion por el clima",
    "2.5.7": "Enfoque de diversidad cultural",
}

# Secciones narrativas obligatorias para validacion
REQUIRED_NARRATIVE_SECTIONS = ["2.1.1", "2.1.2", "2.2.1", "2.2.2", "2.2.3", "2.3.3"]
