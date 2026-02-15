# CooperApp

Aplicacion web para la gestion integral de proyectos de cooperacion internacional, disenada para ONGs espanolas. Permite gestionar el ciclo completo de un proyecto: desde la formulacion y presupuesto, hasta la justificacion economica y generacion de informes para financiadores.

## Stack Tecnologico

| Componente | Tecnologia |
|---|---|
| Backend | **FastAPI** + **Pydantic** |
| ORM | **SQLAlchemy 2.0** |
| Base de datos | **SQLite** |
| Plantillas | **Jinja2** (server-side rendering) |
| Frontend dinamico | **htmx** (actualizaciones parciales sin SPA) |
| Estilos | CSS vanilla con variables (tema Prodiversa `#8B1E3F`) |
| Exportacion | **openpyxl** (Excel) |

## Inicio Rapido

```bash
# Instalar dependencias
pip install -r requirements.txt

# Iniciar servidor de desarrollo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Verificar estado
curl http://localhost:8000/health
```

La aplicacion crea automaticamente la base de datos SQLite (`cooperapp.db`), las tablas, y siembra los datos iniciales (ODS, financiadores, plantillas presupuestarias) al arrancar.

**URLs principales:**
- Aplicacion: `http://localhost:8000/projects`
- API Swagger: `http://localhost:8000/docs`

## Arquitectura General

```
app/
├── main.py              # Entrada FastAPI, lifespan, montaje de routers
├── config.py            # Configuracion via .env (Pydantic Settings)
├── database.py          # Motor SQLAlchemy, sesion, Base
├── models/              # Modelos ORM (SQLAlchemy)
├── schemas/             # Esquemas de validacion (Pydantic)
├── services/            # Logica de negocio
├── routers/api/         # Endpoints REST (/api/*)
├── views/               # Vistas HTML (htmx, TemplateResponse)
├── templates/           # Plantillas Jinja2
│   ├── base.html        # Layout principal
│   ├── components/      # Componentes reutilizables (navbar, cards)
│   ├── pages/           # Paginas completas
│   └── partials/        # Fragmentos HTML para htmx
└── static/              # CSS, JS (htmx.min.js, app.js)
```

**Patron de flujo:** Vista recibe peticion -> Servicio valida y procesa -> Servicio actualiza BD -> Vista devuelve HTML parcial (htmx) o redirige.

Cada modulo sigue la misma estructura: modelo, esquema, servicio, router API, vista HTML y plantillas parciales.

---

## Modulos

### 1. Proyectos (`app/models/project.py`)

Entidad central de la aplicacion. Cada proyecto representa un convenio de cooperacion internacional financiado por una entidad publica.

**Campos principales:**
- `codigo_contable` - Codigo contable unico del proyecto
- `titulo`, `pais`, `sector` - Datos descriptivos
- `financiador` - Entidad financiadora (AACID, AECID, Diputacion Malaga, Ayuntamiento Malaga)
- `tipo` - Desarrollo o Accion Humanitaria
- `estado` - Ciclo de vida: Formulacion -> Aprobado -> Ejecucion -> Justificacion -> Cerrado
- `subvencion` - Importe total de la subvencion (EUR)
- `fecha_inicio`, `fecha_finalizacion`, `fecha_justificacion`
- `cuenta_bancaria` - IBAN del proyecto

**Subentidades:**
- **Plazos** - Hitos y fechas limite con estado de completado
- **ODS** - Vinculacion con los 17 Objetivos de Desarrollo Sostenible de la ONU (relacion muchos-a-muchos)

**Funcionalidad:**
- CRUD completo con filtros por estado, tipo, pais y busqueda de texto
- Estadisticas globales (total proyectos, subvencion acumulada, desglose por estado/tipo/pais)
- Al crear un proyecto, el presupuesto se inicializa automaticamente segun las plantillas del financiador seleccionado
- Si se cambia de financiador, el presupuesto se reinicializa con las nuevas plantillas

---

### 2. Presupuesto (`app/models/budget.py`)

Gestion del presupuesto aprobado y seguimiento de la ejecucion presupuestaria por partida.

**Estructura jerarquica:**

```
Financiador (Funder)
  └── Plantillas de partida (BudgetLineTemplate) - Estructura estandar por financiador
        └── Partidas del proyecto (ProjectBudgetLine) - Instancias por proyecto
```

**Financiadores preconfigurados:**
| Codigo | Nombre | Restricciones |
|---|---|---|
| AACID | Agencia Andaluza de Cooperacion | 20 partidas (A.I.1 a B) |
| AECID | Agencia Espanola de Cooperacion | 12 partidas, max 10% indirectos |
| DIPU | Diputacion de Malaga | 9 partidas, max 8% indirectos |
| AYTO | Ayuntamiento de Malaga | 6 partidas, max 50% personal, max 7% indirectos |

**Cada partida presupuestaria registra:**
- `aprobado` - Importe aprobado
- `ejecutado_espana` - Importe ejecutado en Espana
- `ejecutado_terreno` - Importe ejecutado en terreno (pais destino)
- Propiedades calculadas: `disponible_espana`, `disponible_terreno`, `total_ejecutado`, `porcentaje_ejecucion`

**Alertas automaticas:**
- Presupuesto total supera la subvencion
- Porcentaje de personal supera el limite del financiador
- Costes indirectos superan el maximo permitido
- Desviacion presupuestaria superior al 10%

---

### 3. Gastos / Facturas (`app/models/expense.py`)

Registro y validacion de gastos vinculados a partidas presupuestarias, con seguimiento documental y actualizacion automatica del presupuesto ejecutado.

**Datos de cada gasto:**
- `fecha_factura`, `concepto`, `expedidor`, `persona`
- `cantidad_original`, `moneda_original` (EUR, USD, GBP, MAD, XOF, XAF)
- `tipo_cambio` - Para gastos en moneda extranjera
- `cantidad_euros` - Importe convertido a EUR
- `porcentaje` - Porcentaje de imputacion al proyecto (permite imputacion parcial)
- `cantidad_imputable` - Calculado: `cantidad_euros * porcentaje / 100`
- `ubicacion` - Espana o Terreno
- `financiado_por` - Entidad que financia el gasto
- `documento_path` - Factura digitalizada adjunta

**Maquina de estados:**

```
borrador --> pendiente_revision --> validado --> justificado
                                └-> rechazado
```

- **Borrador**: Editable libremente. Se puede eliminar.
- **Pendiente de revision**: Enviado para su aprobacion.
- **Validado**: Aprobado. Al validar se suma `cantidad_imputable` a `ejecutado_espana` o `ejecutado_terreno` de la partida correspondiente. Requiere documento adjunto.
- **Rechazado**: No aprobado. Se revierte el presupuesto si estaba validado.
- **Justificado**: Incluido en la justificacion final.

Cualquier estado puede revertirse a borrador (con la correspondiente actualizacion del presupuesto).

**Filtros disponibles:** por partida, estado, ubicacion, rango de fechas.

---

### 4. Transferencias (`app/models/transfer.py`)

Gestion de las transferencias bancarias de fondos al pais de ejecucion, con soporte para doble conversion de moneda y seguimiento documental por fase.

**Datos de cada transferencia:**
- `numero` / `total_previstas` - Numero secuencial (ej: "2/5")
- `importe_euros`, `gastos_transferencia`
- Conversion a moneda intermedia (opcional, ej: USD) y moneda local (ej: MAD, XOF, HTG)
- `cuenta_origen` (IBAN), `cuenta_destino`, `entidad_bancaria`
- Documentos de emision y recepcion (path + filename)

**Maquina de estados:**

```
solicitada --> aprobada --> emitida --> recibida --> cerrada
```

- **Solicitada**: Editable y eliminable.
- **Aprobada**: Confirmada para emision.
- **Emitida**: Requiere documento de emision y fecha.
- **Recibida**: Requiere documento de recepcion, con datos de moneda local recibida.
- **Cerrada**: Proceso completado.

**Resumen de transferencias:**
- Presupuesto total del proyecto
- Gastos validados en Espana (restados del presupuesto a transferir)
- Total enviado, gastos de transferencia, pendiente de transferir, porcentaje transferido

**Mapeo automatico de moneda local** segun el pais del proyecto (Haiti->HTG, Marruecos->MAD, Senegal->XOF, etc.).

---

### 5. Marco Logico (`app/models/logical_framework.py`)

Modelado completo de la Matriz del Marco Logico del proyecto, incluyendo seguimiento de indicadores con historial de actualizaciones.

**Estructura jerarquica:**

```
Marco Logico (1 por proyecto)
├── Objetivo General
├── Objetivos Especificos (OE1, OE2...)
│   ├── Indicadores de objetivo
│   └── Resultados (R1, R2...)
│       ├── Indicadores de resultado
│       └── Actividades (A1.1, A1.2...)
│           ├── Indicadores de actividad
│           └── Fuentes de verificacion
└── Indicadores de nivel general
```

**Indicadores:**
- `codigo`, `descripcion`, `unidad_medida`
- `valor_base`, `valor_meta`, `valor_actual`
- `porcentaje_cumplimiento` - Calculado automaticamente si los valores son numericos
- `fuente_verificacion` - Descripcion textual
- Historial de actualizaciones con valor anterior, nuevo, observaciones y fecha

**Actividades:**
- Fechas previstas y reales (inicio/fin)
- Estado: pendiente, en curso, completada, cancelada
- Vinculacion con fuentes de verificacion documentales

---

### 6. Documentos (`app/models/document.py`)

Gestion documental centralizada del proyecto con categorizacion, sellado para justificacion y descarga masiva.

**Categorias de documentos:**
Factura, Comprobante, Fuente de verificacion, Informe, Contrato, Convenio, Acta, Listado de asistencia, Foto, Otro.

**Funcionalidades:**
- Subida de archivos con almacenamiento organizado: `uploads/{project_id}/documents/{categoria}/`
- Metadatos: nombre original, tamano, tipo MIME, descripcion
- **Sellado**: Marca documentos como sellados para la justificacion (con fecha de sellado). Se puede sellar individualmente o masivamente.
- **Descarga ZIP**: Genera un archivo ZIP con todos los documentos del proyecto organizados por categoria.
- Deteccion automatica de tipo (imagen, PDF) para previsualizacion.

---

### 7. Fuentes de Verificacion (`app/models/document.py` - `VerificationSource`)

Vinculacion entre documentos del proyecto y los indicadores o actividades del marco logico, permitiendo verificar el cumplimiento de objetivos.

**Funcionalidad:**
- Vincular un documento a un indicador o actividad especifica
- Tipo de fuente: Foto, Acta, Listado de asistencia, Informe, Certificado, Contrato, Otro
- Estado de validacion (validado/no validado con fecha)

---

### 8. Informes (`app/models/report.py`)

Generacion de informes y exportaciones en formato Excel adaptados a cada financiador.

**Tipos de informe:**
| Tipo | Descripcion |
|---|---|
| Cuenta Justificativa | Resumen economico para justificacion |
| Ejecucion Presupuestaria | Detalle de ejecucion por partida |
| Relacion de Transferencias | Listado de transferencias realizadas |
| Ficha de Proyecto | Resumen general del proyecto |
| Informe Tecnico Mensual | Seguimiento tecnico periodico |
| Informe Economico | Detalle economico completo |

Los informes se generan en formato Excel (.xlsx) usando openpyxl, con formato adaptado a las plantillas de cada financiador.

---

## API REST

Todos los endpoints REST estan bajo el prefijo `/api`. Documentacion interactiva disponible en `/docs` (Swagger).

| Recurso | Prefijo | Operaciones |
|---|---|---|
| Proyectos | `/api/projects` | CRUD, estadisticas |
| Presupuesto | `/api/budget` | Consulta, inicializacion, actualizacion de partidas |
| Gastos | `/api/expenses` | CRUD, cambios de estado, documentos adjuntos |
| Transferencias | `/api/transfers` | CRUD, cambios de estado, documentos de emision/recepcion |
| Marco Logico | `/api/logical-framework` | CRUD jerarquico completo (objetivos, resultados, actividades, indicadores) |
| Documentos | `/api/documents` | CRUD, sellado, descarga ZIP |
| Fuentes de Verificacion | `/api/verification-sources` | CRUD, validacion |
| Informes | `/api/reports` | Generacion, listado, eliminacion |

---

## Frontend (htmx)

La interfaz utiliza htmx para proporcionar una experiencia SPA-like sin JavaScript frameworks. Las interacciones principales son:

- **Pestanas con carga diferida**: Cada modulo (presupuesto, gastos, transferencias, marco logico, documentos, informes) se carga via htmx al hacer clic en su pestana.
- **Modales**: Formularios de creacion/edicion se cargan en modales via `hx-get` y se envian con `hx-post`/`hx-put`.
- **Actualizacion parcial**: Tras crear, editar o eliminar un registro, solo se actualiza la tabla o seccion afectada (`hx-target`, `hx-swap="outerHTML"`).
- **Filtros reactivos**: Los filtros de tablas se aplican automaticamente al cambiar su valor (`hx-trigger="change"`).
- **Confirmacion**: Acciones destructivas requieren confirmacion del usuario (`hx-confirm`).

---

## Configuracion

Variables de entorno configurables via `.env`:

| Variable | Default | Descripcion |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./cooperapp.db` | URL de conexion a la base de datos |
| `APP_NAME` | `CooperApp` | Nombre de la aplicacion |
| `DEBUG` | `True` | Modo debug |
| `APP_PORT` | `8000` | Puerto del servidor |
| `UPLOADS_PATH` | `uploads` | Directorio para archivos subidos |
| `EXPORTS_PATH` | `exports` | Directorio para informes generados |

---

## Despliegue

El proyecto incluye configuracion para despliegue con Docker:

```bash
# Con Docker Compose
docker-compose up -d
```

Archivos de despliegue:
- `Dockerfile` - Imagen de la aplicacion
- `docker-compose.yml` - Orquestacion de servicios
- `nginx/` - Configuracion de Nginx como proxy inverso
- `scripts/deploy.sh` - Script de despliegue automatizado

---

## Datos Iniciales (Seed)

Al iniciar la aplicacion se siembran automaticamente:
1. **17 ODS** (Objetivos de Desarrollo Sostenible de la ONU) con nombres en espanol
2. **4 Financiadores** (AACID, AECID, Diputacion Malaga, Ayuntamiento Malaga) con sus restricciones
3. **Plantillas presupuestarias** para cada financiador (entre 6 y 20 partidas por financiador)
