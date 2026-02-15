# CooperApp - Fase 8: Autenticación, Roles y Auditoría

## Especificación Funcional

**Versión:** 1.0  
**Fecha:** Febrero 2026  
**Cliente:** Prodiversa  
**Proyecto:** CooperApp - Gestión integral de proyectos de cooperación internacional

---

## 1. Visión General

### Descripción

Fase transversal que añade un sistema de autenticación dual a CooperApp: usuarios internos de Prodiversa se autentican mediante Microsoft Entra ID (OAuth 2.0 / OIDC), mientras que las contrapartes locales acceden a un portal independiente utilizando el código del proyecto como credencial. El módulo implementa cinco roles con permisos granulares, asignación manual por el Director, y un sistema completo de auditoría de accesos y acciones.

### Objetivos

1. Integrar autenticación SSO con Microsoft Entra ID para usuarios internos (sede y expatriados)
2. Implementar portal de acceso para contrapartes basado en código de proyecto
3. Definir cinco roles (Director, Coordinador General, Técnico Sede, Gestor País, Contraparte) con permisos granulares por módulo y acción
4. Desarrollar la gestión de usuarios y asignación de roles por parte del Director
5. Implementar sistema de auditoría de accesos y acciones relevantes
6. Asegurar expiración de sesiones y protección de rutas

### Contexto del Cliente

Prodiversa ya dispone de un tenant Microsoft 365. Los técnicos tanto de sede como expatriados comparten el mismo tenant. Las contrapartes son organizaciones socias en los países de ejecución que necesitan acceso limitado para cargar documentación y reportar avances, sin visibilidad sobre datos económicos.

---

## 2. Arquitectura Técnica

### Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Backend | FastAPI + Pydantic |
| ORM | SQLAlchemy 2.0 |
| Base de datos | SQLite |
| Plantillas | Jinja2 (SSR) |
| Frontend dinámico | htmx |
| Autenticación interna | Microsoft Entra ID (OAuth 2.0 / OIDC) |
| Librería OAuth | authlib |
| Sesiones | Cookies firmadas (itsdangerous / starlette sessions) |
| Estilos | CSS vanilla, tema Prodiversa #8B1E3F |

### Estructura de Carpetas (nuevos archivos)

```
app/
├── auth/
│   ├── __init__.py
│   ├── entra.py              # Flujo OAuth con Microsoft Entra ID
│   ├── counterpart.py        # Autenticación por código de proyecto
│   ├── dependencies.py       # Dependencias FastAPI (get_current_user, require_role...)
│   └── session.py            # Gestión de sesiones y cookies
├── models/
│   ├── user.py               # Modelo User
│   ├── counterpart_session.py # Modelo sesión contraparte
│   └── audit_log.py          # Modelo AuditLog
├── schemas/
│   ├── user.py
│   └── audit_log.py
├── services/
│   ├── user.py               # Lógica de negocio usuarios
│   └── audit.py              # Servicio de auditoría
├── routers/api/
│   ├── auth.py               # Endpoints login/logout/callback
│   └── users.py              # CRUD usuarios (admin)
├── views/
│   ├── auth.py               # Vistas login, portal contraparte
│   └── users.py              # Vista gestión usuarios
├── templates/
│   ├── pages/
│   │   ├── auth/
│   │   │   ├── login.html            # Página login interna
│   │   │   ├── counterpart_login.html # Portal contraparte
│   │   │   └── unauthorized.html      # Página sin permisos
│   │   └── users/
│   │       ├── list.html              # Gestión usuarios
│   │       └── detail.html            # Detalle/edición usuario
│   └── partials/
│       ├── auth/
│       │   └── user_menu.html         # Menú usuario logueado
│       └── users/
│           ├── user_row.html
│           └── user_form.html
```

### Flujo de Autenticación

```
┌─────────────────────────────────────────────────────────┐
│                  USUARIOS INTERNOS                       │
│                                                          │
│  Usuario → /login → Redirect Entra ID → Microsoft       │
│  Microsoft → /auth/callback → Crear/actualizar User     │
│  → Crear sesión → Redirect /dashboard                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   CONTRAPARTES                           │
│                                                          │
│  Contraparte → /contraparte/login → Introduce código    │
│  → Validar código contra PROJECT.codigo_contable        │
│  → Crear sesión limitada → Redirect /contraparte/{id}   │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Modelo de Datos

### Diagrama E-R

```
┌──────────────────────────────┐
│            USER              │
├──────────────────────────────┤
│ id (PK, UUID)                │
│ email (UNIQUE, String)       │
│ nombre (String)              │
│ apellidos (String)           │
│ entra_oid (UNIQUE, String)   │     ┌─────────────────────────┐
│ rol (Enum)                   │     │    USER_PROJECT         │
│ activo (Bool, default=True)  │     ├─────────────────────────┤
│ ultimo_acceso (DateTime)     │◄───▶│ user_id (FK → USER)     │
│ created_at (DateTime)        │ M:N │ project_id (FK → PROJ.) │
│ updated_at (DateTime)        │     └─────────────────────────┘
└──────────────────────────────┘
           Solo para rol = gestor_pais

┌──────────────────────────────┐
│    COUNTERPART_SESSION       │
├──────────────────────────────┤
│ id (PK, UUID)                │
│ project_id (FK → PROJECT)    │
│ session_token (UNIQUE, Str)  │
│ ip_address (String)          │
│ user_agent (String)          │
│ created_at (DateTime)        │
│ expires_at (DateTime)        │
│ last_activity (DateTime)     │
│ activo (Bool, default=True)  │
└──────────────────────────────┘

┌──────────────────────────────┐
│         AUDIT_LOG            │
├──────────────────────────────┤
│ id (PK, UUID)                │
│ timestamp (DateTime, index)  │
│ actor_type (Enum)            │  ← internal / counterpart
│ actor_id (String)            │  ← user.id o session.id
│ actor_email (String, null.)  │
│ actor_label (String)         │  ← nombre o "Contraparte PRD-001"
│ accion (Enum)                │
│ recurso (String)             │  ← "project", "expense", etc.
│ recurso_id (String, null.)   │
│ detalle (JSON, nullable)     │  ← datos extra según acción
│ ip_address (String)          │
│ project_id (FK, nullable)    │  ← contexto proyecto si aplica
└──────────────────────────────┘
```

### Definición de Tablas

#### USER

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | UUID (PK) | Identificador único |
| email | String, UNIQUE, NOT NULL | Email corporativo Microsoft |
| nombre | String, NOT NULL | Nombre del usuario |
| apellidos | String, NOT NULL | Apellidos |
| entra_oid | String, UNIQUE, NOT NULL | Object ID de Microsoft Entra ID |
| rol | Enum(director, coordinador, tecnico_sede, gestor_pais) | Rol asignado |
| activo | Boolean, default True | Si el usuario puede acceder |
| ultimo_acceso | DateTime, nullable | Última fecha de login |
| created_at | DateTime | Fecha de creación |
| updated_at | DateTime | Última modificación |

#### USER_PROJECT (tabla asociativa)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| user_id | UUID (FK → USER), PK | Usuario gestor |
| project_id | Integer (FK → PROJECT), PK | Proyecto asignado |

Solo se utiliza para usuarios con rol `gestor_pais`. Los demás roles tienen acceso a todos los proyectos por definición.

#### COUNTERPART_SESSION

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | UUID (PK) | Identificador de sesión |
| project_id | Integer (FK → PROJECT), NOT NULL | Proyecto al que accede |
| session_token | String, UNIQUE, NOT NULL | Token de sesión generado |
| ip_address | String | IP de conexión |
| user_agent | String | Navegador/dispositivo |
| created_at | DateTime | Inicio de sesión |
| expires_at | DateTime | Expiración de sesión (created_at + 8h) |
| last_activity | DateTime | Última actividad registrada |
| activo | Boolean, default True | Si la sesión sigue viva |

#### AUDIT_LOG

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | UUID (PK) | Identificador |
| timestamp | DateTime, index | Momento del evento |
| actor_type | Enum(internal, counterpart) | Tipo de actor |
| actor_id | String | ID del user o de la sesión contraparte |
| actor_email | String, nullable | Email (solo internos) |
| actor_label | String | Etiqueta legible: "Ana García" o "Contraparte PRD-001" |
| accion | Enum | Acción realizada (ver tabla abajo) |
| recurso | String | Tipo de recurso afectado |
| recurso_id | String, nullable | ID del recurso |
| detalle | JSON, nullable | Datos adicionales según acción |
| ip_address | String | IP del actor |
| project_id | Integer (FK), nullable | Proyecto relacionado si aplica |

#### Acciones de Auditoría (Enum)

| Acción | Descripción |
|--------|-------------|
| login | Inicio de sesión |
| logout | Cierre de sesión |
| login_failed | Intento fallido |
| session_expired | Sesión expirada automáticamente |
| create | Crear recurso |
| update | Modificar recurso |
| delete | Eliminar recurso |
| status_change | Cambio de estado (gastos, transferencias) |
| upload | Subir documento |
| download | Descargar documento/informe |
| export | Generar informe |
| role_change | Cambio de rol de usuario |
| project_assign | Asignar proyecto a gestor |
| project_unassign | Desasignar proyecto |

---

## 4. Flujos de Trabajo

### Flujo 1: Login Interno (Microsoft Entra ID)

```
Usuario                CooperApp              Microsoft Entra ID
  │                        │                          │
  │──── GET /login ───────▶│                          │
  │                        │── Redirect ─────────────▶│
  │                        │   /authorize?             │
  │                        │   client_id=XXX&          │
  │                        │   redirect_uri=XXX&       │
  │                        │   scope=openid email      │
  │                        │   profile&                │
  │                        │   response_type=code      │
  │◀─────────────────────────────── Login Microsoft ──│
  │──── Credenciales ──────────────────────────────── │
  │                        │◀── Callback + code ──────│
  │                        │                          │
  │                        │── POST /token ──────────▶│
  │                        │◀── access_token + ───────│
  │                        │    id_token              │
  │                        │                          │
  │                        │── Decodificar id_token   │
  │                        │   Extraer: oid, email,   │
  │                        │   name                   │
  │                        │                          │
  │                        │── ¿Existe User con oid?  │
  │                        │   SÍ → Actualizar datos  │
  │                        │   NO → Crear User con    │
  │                        │   rol=NULL (pendiente)    │
  │                        │                          │
  │                        │── ¿User.activo = True    │
  │                        │   AND User.rol != NULL?   │
  │                        │   SÍ → Crear sesión      │
  │                        │   NO → Página "pendiente  │
  │                        │         de activación"    │
  │                        │                          │
  │◀── Set-Cookie + ──────│                          │
  │    Redirect /dashboard │                          │
  │                        │── AuditLog: login        │
```

### Flujo 2: Login Contraparte

```
Contraparte            CooperApp
  │                        │
  │── GET /contraparte ───▶│
  │◀── Formulario código ──│
  │                        │
  │── POST código ────────▶│
  │                        │── ¿Existe PROJECT con
  │                        │   codigo_contable = input
  │                        │   AND estado IN
  │                        │   (ejecucion, justif.)?
  │                        │
  │                        │   NO → Error "Código
  │                        │   no válido o proyecto
  │                        │   no activo"
  │                        │
  │                        │   SÍ → Crear
  │                        │   COUNTERPART_SESSION
  │                        │   (expires_at = now+8h)
  │                        │
  │◀── Set-Cookie + ──────│
  │    Redirect             │
  │    /contraparte/{id}   │
  │                        │── AuditLog: login
  │                        │   (counterpart)
```

### Flujo 3: Primer Login Interno (usuario nuevo)

```
1. Usuario accede por primera vez via Microsoft
2. CooperApp crea User con entra_oid, email, nombre
   → rol = NULL, activo = True
3. Se muestra página "Tu cuenta está pendiente de activación.
   El administrador asignará tu rol pronto."
4. Se registra AuditLog: login (con detalle "primer_login")
5. Director accede a /usuarios, ve usuario pendiente
6. Director asigna rol (y proyectos si es gestor_pais)
7. Se registra AuditLog: role_change
8. Usuario vuelve a acceder → acceso normal
```

### Flujo 4: Verificación de Permisos (Middleware)

```
Request entrante
      │
      ▼
  ¿Ruta pública?  ──SÍ──▶ Procesar
      │ NO
      ▼
  ¿Ruta /contraparte/*?
      │ SÍ                          │ NO
      ▼                              ▼
  Validar cookie              Validar cookie
  contraparte                 interna
      │                              │
      ▼                              ▼
  ¿Session válida          ¿User válido
   y no expirada?           y activo?
      │                              │
   NO → /contraparte/login    NO → /login
      │                              │
   SÍ → Verificar que         SÍ → Verificar rol
   solo accede a su               vs permisos ruta
   proyecto                        │
      │                        NO → /unauthorized
      ▼                              │
  Actualizar                   SÍ → Procesar
  last_activity                     │
      │                        ¿Gestor_pais?
      ▼                        SÍ → Verificar
  Procesar                     proyecto asignado
                                    │
                               NO → /unauthorized
                                    │
                               SÍ → Procesar
```

---

## 5. API Endpoints

### Autenticación

| Método | Ruta | Descripción | Acceso |
|--------|------|-------------|--------|
| GET | /login | Página de login interno | Público |
| GET | /auth/callback | Callback OAuth de Microsoft | Público (redirect) |
| POST | /auth/logout | Cerrar sesión interna | Autenticado |
| GET | /contraparte/login | Página login contraparte | Público |
| POST | /contraparte/login | Validar código de proyecto | Público |
| POST | /contraparte/logout | Cerrar sesión contraparte | Contraparte |

### Gestión de Usuarios (solo Director)

| Método | Ruta | Descripción | Acceso |
|--------|------|-------------|--------|
| GET | /api/users | Listar usuarios | Director |
| GET | /api/users/{id} | Detalle usuario | Director |
| PUT | /api/users/{id}/role | Cambiar rol | Director |
| PUT | /api/users/{id}/toggle-active | Activar/desactivar | Director |
| POST | /api/users/{id}/projects | Asignar proyecto(s) a gestor | Director |
| DELETE | /api/users/{id}/projects/{pid} | Desasignar proyecto | Director |

### Vistas HTML de Usuarios

| Método | Ruta | Descripción | Acceso |
|--------|------|-------------|--------|
| GET | /usuarios | Lista de usuarios (gestión) | Director |
| GET | /usuarios/{id} | Ficha de usuario | Director |

### Auditoría

| Método | Ruta | Descripción | Acceso |
|--------|------|-------------|--------|
| GET | /api/audit-log | Listar eventos (paginado) | Director |
| GET | /api/audit-log?project_id=X | Filtrar por proyecto | Director |
| GET | /api/audit-log?actor_id=X | Filtrar por actor | Director |
| GET | /api/audit-log?accion=X | Filtrar por acción | Director |
| GET | /api/audit-log?desde=X&hasta=Y | Filtrar por rango fechas | Director |

### Vista HTML de Auditoría

| Método | Ruta | Descripción | Acceso |
|--------|------|-------------|--------|
| GET | /auditoria | Log de auditoría con filtros | Director |

---

## 6. Interfaz de Usuario

### Navegación Base (actualizada)

```
┌─────────────────────────────────────────────────────────────────┐
│  [Logo Prodiversa]  CooperApp                                    │
│                                                                   │
│  [Proyectos] [+Nuevo]              [👤 Ana García ▼]            │
│                                      ├── Mi perfil               │
│                                      ├── Usuarios (solo Dir.)    │
│                                      ├── Auditoría (solo Dir.)   │
│                                      └── Cerrar sesión           │
├─────────────────────────────────────────────────────────────────┤
│  (contenido según rol y ruta)                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Login Interno

```
┌─────────────────────────────────────────────┐
│                                              │
│            [Logo Prodiversa]                 │
│              CooperApp                       │
│                                              │
│   ┌──────────────────────────────────┐      │
│   │                                  │      │
│   │   Acceso para personal de        │      │
│   │   Prodiversa                     │      │
│   │                                  │      │
│   │   [🔑 Iniciar sesión con        │      │
│   │        Microsoft]                │      │
│   │                                  │      │
│   └──────────────────────────────────┘      │
│                                              │
│   ¿Eres contraparte de un proyecto?         │
│   [Accede aquí →]                            │
│                                              │
└─────────────────────────────────────────────┘
```

### Login Contraparte

```
┌─────────────────────────────────────────────┐
│                                              │
│            [Logo Prodiversa]                 │
│          CooperApp · Contrapartes            │
│                                              │
│   ┌──────────────────────────────────┐      │
│   │                                  │      │
│   │   Introduce el código de tu      │      │
│   │   proyecto para acceder:         │      │
│   │                                  │      │
│   │   Código: [PRD-___________]      │      │
│   │                                  │      │
│   │           [Acceder]              │      │
│   │                                  │      │
│   │   ⚠ Código no válido (oculto)   │      │
│   └──────────────────────────────────┘      │
│                                              │
│   ¿Eres personal de Prodiversa?             │
│   [Inicia sesión aquí →]                     │
│                                              │
└─────────────────────────────────────────────┘
```

### Gestión de Usuarios (Director)

```
┌─────────────────────────────────────────────────────────────┐
│  Gestión de Usuarios                         [Auditoría →]   │
│                                                               │
│  Filtros: [Rol ▼] [Estado ▼] [Buscar...  ]                  │
│  ─────────────────────────────────────────────────────────── │
│  │ Nombre         │ Email              │ Rol        │ Estado │
│  │ Ana García     │ ana@prodiversa.org │ Director   │ ●Activo│
│  │ Pedro López    │ pedro@prodi...     │ Gestor País│ ●Activo│
│  │ Nuevo Usuario  │ nuevo@prodi...     │ ⚠ Sin rol  │ Pend. │
│  └────────────────┴────────────────────┴────────────┴───────┘ │
│                                                               │
│  Click en usuario →                                           │
│  ┌────────────────────────────────────────┐                  │
│  │ Pedro López                            │                  │
│  │ pedro@prodiversa.org                   │                  │
│  │                                        │                  │
│  │ Rol: [Gestor País ▼]   [Guardar]      │                  │
│  │ Estado: [●Activo / ○Inactivo]          │                  │
│  │                                        │                  │
│  │ Proyectos asignados:                   │                  │
│  │  ✕ PRD-001 Agua potable Senegal       │                  │
│  │  ✕ PRD-003 Salud Haití               │                  │
│  │  [+ Asignar proyecto ▼]               │                  │
│  │                                        │                  │
│  │ Último acceso: 12/02/2026 09:34       │                  │
│  └────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### Log de Auditoría (Director)

```
┌─────────────────────────────────────────────────────────────────┐
│  Auditoría de Accesos y Acciones                                 │
│                                                                   │
│  Filtros: [Acción ▼] [Usuario ▼] [Proyecto ▼]                   │
│           [Desde: __/__/__] [Hasta: __/__/__]                    │
│  ──────────────────────────────────────────────────────────────  │
│  │ Fecha/Hora        │ Actor          │ Acción      │ Detalle  │ │
│  │ 13/02 10:15:03    │ Ana García     │ login       │ IP: ...  │ │
│  │ 13/02 10:16:45    │ Ana García     │ role_change │ Pedro →  │ │
│  │                   │                │             │ gestor   │ │
│  │ 13/02 10:20:11    │ Contr. PRD-001 │ upload      │ factu... │ │
│  │ 13/02 10:22:00    │ Pedro López    │ update      │ expense  │ │
│  │                   │                │             │ #45      │ │
│  └────────────────────┴────────────────┴─────────────┴──────────┘ │
│                                                                   │
│  Mostrando 1-50 de 1.234           [← Anterior] [Siguiente →]   │
└─────────────────────────────────────────────────────────────────┘
```

### Portal Contraparte (vista limitada)

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo Prodiversa]  CooperApp          Proyecto: PRD-001    │
│                                        [Cerrar sesión]       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Proyecto: Agua potable rural - Senegal                      │
│                                                               │
│  [Marco Lógico] [Documentos] [Actividades]                   │
│                                                               │
│  (Solo módulos técnicos: marco lógico, documentos,           │
│   actividades. Sin datos económicos.)                         │
│                                                               │
│  ⏱ Sesión expira en: 6h 23min                                │
└─────────────────────────────────────────────────────────────┘
```

### Notas de UX

- El botón de Microsoft sigue la guía de marca de Microsoft (logo + texto)
- Los mensajes de error de login de contraparte son genéricos para no revelar si el código existe
- El indicador de expiración de sesión en el portal contraparte se actualiza por htmx cada minuto
- Los usuarios sin rol ven una página amigable explicando que su cuenta está pendiente
- Los cambios de rol y asignación de proyectos se hacen con htmx (sin recarga completa)

---

## 7. Lógica de Negocio

### Matriz de Permisos

```
Leyenda:  ✅ = Total  👁 = Solo lectura  🔒 = Solo asignados  ❌ = Sin acceso
          📝 = Crear/editar  ✓ = Limitado

                        Director  Coordinador  Técnico   Gestor    Contraparte
                                  General      Sede      País

Proyectos (ver)           ✅         ✅          ✅       🔒         🔒 (1 proy.)
Proyectos (crear)         ✅         ✅          ❌       ❌         ❌
Proyectos (editar)        ✅         ✅          📝       📝 (*)     ❌
Proyectos (eliminar)      ✅         ❌          ❌       ❌         ❌

Presupuesto (ver)         ✅         ✅          ✅       🔒         ❌
Presupuesto (editar)      ✅         ✅          📝       ❌         ❌

Gastos (ver)              ✅         ✅          ✅       🔒         ❌
Gastos (crear/editar)     ✅         ✅          📝       📝 (*)     ❌
Gastos (validar)          ✅         ✅          📝       ❌         ❌
Gastos (justificar)       ✅         ✅          📝       ❌         ❌

Transferencias (ver)      ✅         ✅          ✅       🔒         ❌
Transferencias (gestión)  ✅         ✅          📝       ❌         ❌

Marco Lógico (ver)        ✅         ✅          ✅       🔒         👁
Marco Lógico (editar)     ✅         ✅          📝       📝 (*)     ❌
Marco Lógico (indicad.)   ✅         ✅          📝       📝 (*)     ❌

Documentos (ver)          ✅         ✅          ✅       🔒         👁 (parcial)
Documentos (subir)        ✅         ✅          📝       📝 (*)     📝 (limitado)
Documentos (sellar)       ✅         ✅          📝       ❌         ❌
Documentos (validar FV)   ✅         ✅          📝       ❌         ❌

Informes (generar)        ✅         ✅          📝       👁         ❌
Informes (descargar)      ✅         ✅          ✅       🔒         ❌

Usuarios (gestión)        ✅         ❌          ❌       ❌         ❌
Auditoría (ver)           ✅         ❌          ❌       ❌         ❌
Dashboard global          ✅         ✅          ✅       ❌         ❌
```

**(*) Gestor País**: Solo puede actuar sobre proyectos que tiene asignados. No puede editar datos de justificación final (campos `fecha_justificacion`, estados `justificado`).

### Lógica de Permisos (código ejemplo)

```python
from enum import Enum
from functools import wraps
from fastapi import HTTPException, Depends

class Rol(str, Enum):
    director = "director"
    coordinador = "coordinador"
    tecnico_sede = "tecnico_sede"
    gestor_pais = "gestor_pais"

class Permiso(str, Enum):
    # Proyectos
    proyecto_ver = "proyecto_ver"
    proyecto_crear = "proyecto_crear"
    proyecto_editar = "proyecto_editar"
    proyecto_eliminar = "proyecto_eliminar"
    # Presupuesto
    presupuesto_ver = "presupuesto_ver"
    presupuesto_editar = "presupuesto_editar"
    # Gastos
    gasto_ver = "gasto_ver"
    gasto_crear = "gasto_crear"
    gasto_validar = "gasto_validar"
    gasto_justificar = "gasto_justificar"
    # Transferencias
    transferencia_ver = "transferencia_ver"
    transferencia_gestionar = "transferencia_gestionar"
    # Marco Lógico
    marco_ver = "marco_ver"
    marco_editar = "marco_editar"
    # Documentos
    documento_ver = "documento_ver"
    documento_subir = "documento_subir"
    documento_sellar = "documento_sellar"
    # Informes
    informe_generar = "informe_generar"
    informe_descargar = "informe_descargar"
    # Admin
    usuarios_gestionar = "usuarios_gestionar"
    auditoria_ver = "auditoria_ver"
    dashboard_global = "dashboard_global"

# Mapeo rol → permisos
PERMISOS_POR_ROL: dict[Rol, set[Permiso]] = {
    Rol.director: set(Permiso),  # Todos los permisos
    Rol.coordinador: {
        Permiso.proyecto_ver, Permiso.proyecto_crear,
        Permiso.proyecto_editar,
        Permiso.presupuesto_ver, Permiso.presupuesto_editar,
        Permiso.gasto_ver, Permiso.gasto_crear,
        Permiso.gasto_validar, Permiso.gasto_justificar,
        Permiso.transferencia_ver, Permiso.transferencia_gestionar,
        Permiso.marco_ver, Permiso.marco_editar,
        Permiso.documento_ver, Permiso.documento_subir,
        Permiso.documento_sellar,
        Permiso.informe_generar, Permiso.informe_descargar,
        Permiso.dashboard_global,
    },
    Rol.tecnico_sede: {
        Permiso.proyecto_ver, Permiso.proyecto_editar,
        Permiso.presupuesto_ver, Permiso.presupuesto_editar,
        Permiso.gasto_ver, Permiso.gasto_crear,
        Permiso.gasto_validar, Permiso.gasto_justificar,
        Permiso.transferencia_ver, Permiso.transferencia_gestionar,
        Permiso.marco_ver, Permiso.marco_editar,
        Permiso.documento_ver, Permiso.documento_subir,
        Permiso.documento_sellar,
        Permiso.informe_generar, Permiso.informe_descargar,
        Permiso.dashboard_global,
    },
    Rol.gestor_pais: {
        Permiso.proyecto_ver, Permiso.proyecto_editar,
        Permiso.gasto_ver, Permiso.gasto_crear,
        Permiso.presupuesto_ver,
        Permiso.transferencia_ver,
        Permiso.marco_ver, Permiso.marco_editar,
        Permiso.documento_ver, Permiso.documento_subir,
        Permiso.informe_descargar,
    },
}


def require_permission(permiso: Permiso):
    """Dependencia FastAPI que verifica permiso."""
    async def checker(user = Depends(get_current_user)):
        if permiso not in PERMISOS_POR_ROL.get(user.rol, set()):
            raise HTTPException(status_code=403)
        return user
    return Depends(checker)


async def check_project_access(user, project_id: int, db):
    """Verificar que un gestor_pais tiene acceso al proyecto."""
    if user.rol == Rol.gestor_pais:
        assigned = await db.execute(
            select(UserProject)
            .where(UserProject.user_id == user.id)
            .where(UserProject.project_id == project_id)
        )
        if not assigned.scalar_one_or_none():
            raise HTTPException(status_code=403)
```

### Lógica de Sesión de Contraparte

```python
COUNTERPART_SESSION_DURATION = timedelta(hours=8)
COUNTERPART_INACTIVITY_TIMEOUT = timedelta(hours=2)

async def validate_counterpart_session(session_token: str, db) -> CounterpartSession:
    session = await db.get_by_token(session_token)

    if not session or not session.activo:
        raise HTTPException(status_code=401)

    now = datetime.utcnow()

    # Expiración absoluta (8 horas desde creación)
    if now > session.expires_at:
        session.activo = False
        await audit_log(accion="session_expired", ...)
        raise HTTPException(status_code=401)

    # Expiración por inactividad (2 horas)
    if now - session.last_activity > COUNTERPART_INACTIVITY_TIMEOUT:
        session.activo = False
        await audit_log(accion="session_expired", ...)
        raise HTTPException(status_code=401)

    # Actualizar última actividad
    session.last_activity = now
    await db.commit()
    return session
```

### Servicio de Auditoría

```python
async def audit_log(
    db,
    actor_type: str,       # "internal" | "counterpart"
    actor_id: str,
    actor_label: str,
    accion: str,
    recurso: str = None,
    recurso_id: str = None,
    detalle: dict = None,
    ip_address: str = None,
    project_id: int = None,
):
    log = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        actor_label=actor_label,
        accion=accion,
        recurso=recurso,
        recurso_id=recurso_id,
        detalle=detalle,
        ip_address=ip_address,
        project_id=project_id,
    )
    db.add(log)
    await db.commit()
```

### Restricciones del Gestor de País

El gestor de país tiene restricciones específicas que se verifican a nivel de servicio:

1. **Acceso a proyectos**: Solo los que tiene en `USER_PROJECT`
2. **No puede editar justificación**: Los campos `fecha_justificacion` y las transiciones de estado a `justificado` están bloqueados
3. **No puede validar gastos**: Solo puede crear y editar gastos en estado `borrador`
4. **No puede gestionar transferencias**: Solo vista de lectura
5. **No puede sellar documentos**: Solo subir

---

## 8. Integraciones

### Microsoft Entra ID (OAuth 2.0 / OIDC)

| Parámetro | Valor |
|-----------|-------|
| Authority | `https://login.microsoftonline.com/{tenant_id}/v2.0` |
| Client ID | Variable de entorno `ENTRA_CLIENT_ID` |
| Client Secret | Variable de entorno `ENTRA_CLIENT_SECRET` |
| Redirect URI | `{APP_URL}/auth/callback` |
| Scopes | `openid`, `email`, `profile` |
| Response type | `code` (Authorization Code Flow) |

**Variables de entorno (.env):**

```
ENTRA_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ENTRA_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ENTRA_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
APP_URL=https://cooperapp.prodiversa.org
SESSION_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Datos extraídos del token:**

| Claim | Campo User |
|-------|-----------|
| oid | entra_oid |
| preferred_username / email | email |
| given_name | nombre |
| family_name | apellidos |

### Librería recomendada: authlib

```python
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()
oauth.register(
    name="entra",
    client_id=settings.ENTRA_CLIENT_ID,
    client_secret=settings.ENTRA_CLIENT_SECRET,
    server_metadata_url=(
        f"https://login.microsoftonline.com/"
        f"{settings.ENTRA_TENANT_ID}/v2.0/.well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid email profile"},
)
```

---

## 9. Plan de Desarrollo

### Sprint 1: Autenticación (1 semana)

- Configurar authlib con Microsoft Entra ID
- Implementar flujo OAuth completo (login → callback → sesión)
- Crear modelo User con campos de Entra ID
- Implementar login/logout internos
- Crear portal de contraparte con acceso por código
- Implementar modelo CounterpartSession con expiración
- Crear páginas de login (interna y contraparte)
- Crear página de "pendiente de activación"

### Sprint 2: Roles, Permisos y Gestión (1 semana)

- Implementar sistema de permisos (enum + mapeo por rol)
- Crear dependencias FastAPI para verificación de permisos
- Crear middleware de protección de rutas
- Implementar restricciones de gestor_pais (proyecto asignado)
- Crear interfaz de gestión de usuarios (Director)
- Implementar asignación de roles y proyectos
- Crear tabla USER_PROJECT y lógica asociada
- Actualizar navegación base con menú de usuario y condicionales de rol

### Sprint 3: Auditoría y Refinamiento (1 semana)

- Implementar modelo AuditLog
- Crear servicio de auditoría
- Instrumentar todos los endpoints existentes con logging
- Crear interfaz de consulta de auditoría con filtros
- Implementar restricciones de contraparte (sin datos económicos)
- Actualizar portal de contraparte con vistas limitadas
- Testing de permisos por rol
- Pruebas de sesión y expiración

### Estimación Total

| Sprint | Contenido | Semanas |
|--------|-----------|---------|
| 1 | Autenticación dual (Entra + contraparte) | 1 |
| 2 | Roles, permisos y gestión de usuarios | 1 |
| 3 | Auditoría y refinamiento | 1 |
| **Total** | | **~3 semanas** |

---

## 10. Conexiones con Otras Fases

### Impacto en Fases Existentes

Esta fase es **transversal** y afecta a todas las fases anteriores:

| Fase | Impacto |
|------|---------|
| Fase 1 (Proyectos) | Filtrar proyectos según rol. Gestor solo ve asignados. Contraparte ve 1 proyecto. |
| Fase 2 (Presupuesto) | Contraparte sin acceso. Gestor solo lectura. |
| Fase 3 (Gastos) | Contraparte sin acceso. Gestor crea pero no valida/justifica. |
| Fase 4 (Transferencias) | Contraparte sin acceso. Gestor solo lectura. |
| Fase 5 (Marco Lógico) | Contraparte puede ver. Gestor puede editar en sus proyectos. |
| Fase 6 (Documentos) | Contraparte puede ver parcialmente y subir. Gestor sube pero no sella. |
| Fase 7 (Informes) | Contraparte sin acceso. Gestor descarga de sus proyectos. |

### Datos Compartidos

- `PROJECT.codigo_contable` → Usado como credencial de acceso para contrapartes
- `PROJECT.estado` → Solo proyectos en ejecución/justificación permiten acceso a contraparte
- Todos los endpoints existentes deben incorporar verificación de permisos
