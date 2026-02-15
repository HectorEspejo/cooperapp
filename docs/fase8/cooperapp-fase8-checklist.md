# CooperApp - Checklist Fase 8: Autenticación, Roles y Auditoría

## Modelos de Datos
- [x] Modelo USER con campos: id, email, nombre, apellidos, entra_oid, rol, activo, ultimo_acceso, timestamps
- [x] Enum Rol: director, coordinador, tecnico_sede, gestor_pais
- [x] Tabla USER_PROJECT (asociativa user_id + project_id)
- [x] Modelo COUNTERPART_SESSION con campos: id, project_id, session_token, ip, user_agent, timestamps, expires_at, activo
- [x] Modelo AUDIT_LOG con campos: id, timestamp, actor_type, actor_id, actor_email, actor_label, accion, recurso, recurso_id, detalle (JSON), ip, project_id
- [x] Enum de acciones de auditoría (login, logout, create, update, delete, status_change, upload, download, export, role_change, project_assign, project_unassign, login_failed, session_expired)
- [x] Migraciones/creación automática de tablas nuevas

## Autenticación Microsoft Entra ID
- [x] Configurar authlib con OAuth 2.0 / OIDC
- [x] Variables de entorno: ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, APP_URL, SESSION_SECRET_KEY
- [x] Endpoint GET /login con redirect a Microsoft
- [x] Endpoint GET /auth/callback que procesa el code y obtiene tokens
- [x] Decodificar id_token y extraer: oid, email, nombre, apellidos
- [x] Primer login: crear User con rol=NULL, activo=True
- [x] Login recurrente: actualizar datos del usuario desde token
- [x] Verificar user.activo=True y user.rol!=NULL para permitir acceso
- [x] Página "pendiente de activación" para usuarios sin rol asignado
- [x] Crear sesión con cookie firmada tras login exitoso
- [x] Endpoint POST /auth/logout que destruye la sesión
- [x] Actualizar campo ultimo_acceso en cada login

## Autenticación Contraparte
- [x] Página de login contraparte en /contraparte/login
- [x] Formulario con campo de código de proyecto
- [x] Validar código contra PROJECT.codigo_contable
- [x] Verificar que el proyecto está en estado ejecución o justificación
- [x] Mensaje de error genérico (no revelar si código existe)
- [x] Crear COUNTERPART_SESSION con token, IP, user_agent
- [x] Expiración absoluta: 8 horas desde creación
- [x] Expiración por inactividad: 2 horas sin actividad
- [x] Actualizar last_activity en cada request
- [x] Desactivar sesión expirada automáticamente
- [x] Cookie separada para sesión de contraparte
- [x] Endpoint POST /contraparte/logout
- [x] Indicador de tiempo restante de sesión en portal contraparte (htmx polling)

## Sistema de Roles y Permisos
- [x] Enum Permiso con todos los permisos definidos (proyecto_ver, proyecto_crear, proyecto_editar, proyecto_eliminar, presupuesto_ver, presupuesto_editar, gasto_ver, gasto_crear, gasto_validar, gasto_justificar, transferencia_ver, transferencia_gestionar, marco_ver, marco_editar, documento_ver, documento_subir, documento_sellar, informe_generar, informe_descargar, usuarios_gestionar, auditoria_ver, dashboard_global)
- [x] Mapeo PERMISOS_POR_ROL: director (todos), coordinador (sin admin), tecnico_sede (sin crear proyectos/admin), gestor_pais (limitado)
- [x] Dependencia FastAPI require_permission(permiso)
- [x] Función check_project_access para gestor_pais (verificar USER_PROJECT)
- [x] Restricción gestor_pais: no puede editar fecha_justificacion
- [x] Restricción gestor_pais: no puede transicionar gastos a validado/justificado
- [x] Restricción gestor_pais: no puede sellar documentos
- [x] Restricción gestor_pais: no puede gestionar transferencias (solo lectura)
- [x] Restricción contraparte: sin acceso a datos económicos (presupuesto, gastos, transferencias)
- [x] Restricción contraparte: acceso solo a marco lógico, documentos parcial, actividades

## Protección de Rutas (Middleware)
- [x] Middleware de autenticación para rutas internas
- [x] Middleware de autenticación para rutas de contraparte (/contraparte/*)
- [x] Rutas públicas excluidas: /login, /auth/callback, /contraparte/login, /static
- [x] Redirect a /login si sesión interna inválida
- [x] Redirect a /contraparte/login si sesión contraparte inválida
- [x] Verificación de permisos por ruta según rol
- [x] Página /unauthorized para accesos denegados
- [x] Contraparte solo puede acceder a su proyecto (verificar project_id en sesión)

## Gestión de Usuarios (Director)
- [x] Vista GET /usuarios con tabla de todos los usuarios
- [x] Filtros: por rol, por estado (activo/inactivo/pendiente), búsqueda por nombre/email
- [x] Detalle de usuario con formulario de edición
- [x] Cambiar rol de usuario (select con enum)
- [x] Activar/desactivar usuario (toggle)
- [x] Asignar proyectos a gestor_pais (select de proyectos disponibles)
- [x] Desasignar proyecto de gestor_pais (botón eliminar)
- [x] Mostrar lista de proyectos asignados en detalle de usuario
- [x] Mostrar último acceso del usuario
- [x] Indicador visual de usuarios pendientes (sin rol)
- [x] Interacciones via htmx (sin recarga completa)

## Auditoría
- [x] Servicio audit_log() que registra eventos en AUDIT_LOG
- [x] Registrar login exitoso (interno y contraparte)
- [x] Registrar login fallido (código contraparte inválido)
- [x] Registrar logout
- [x] Registrar expiración de sesión
- [x] Registrar creación de recursos (proyectos, gastos, transferencias, etc.)
- [x] Registrar modificación de recursos
- [x] Registrar eliminación de recursos
- [x] Registrar cambios de estado (gastos, transferencias)
- [x] Registrar subida de documentos
- [x] Registrar descarga de documentos/informes
- [x] Registrar generación de informes
- [x] Registrar cambios de rol
- [x] Registrar asignación/desasignación de proyectos
- [x] Vista GET /auditoria con tabla paginada de eventos
- [x] Filtros: por acción, por actor, por proyecto, por rango de fechas
- [x] Paginación de resultados
- [x] Solo accesible por Director

## Interfaz de Usuario
- [x] Página login interna con botón "Iniciar sesión con Microsoft" (guía de marca Microsoft)
- [x] Enlace a portal contraparte desde login interno
- [x] Página login contraparte con campo código y botón acceder
- [x] Enlace a login interno desde portal contraparte
- [x] Menú de usuario en navbar (nombre + dropdown con perfil, admin, logout)
- [x] Mostrar/ocultar opciones de menú según rol (Usuarios, Auditoría solo Director)
- [x] Página "pendiente de activación" amigable
- [x] Página /unauthorized con mensaje claro
- [x] Portal contraparte con navegación limitada (Marco Lógico, Documentos, Actividades)
- [x] Indicador de expiración de sesión en portal contraparte
- [x] Ocultar botón +Nuevo Proyecto para roles sin permiso
- [x] Ocultar acciones de validación/justificación según permisos
- [x] Ocultar pestañas económicas en portal contraparte
- [x] Loading states en interacciones de gestión de usuarios

## API Endpoints
- [x] GET /login
- [x] GET /auth/callback
- [x] POST /auth/logout
- [x] GET /contraparte/login
- [x] POST /contraparte/login
- [x] POST /contraparte/logout
- [x] GET /api/users (Director)
- [x] GET /api/users/{id} (Director)
- [x] PUT /api/users/{id}/role (Director)
- [x] PUT /api/users/{id}/toggle-active (Director)
- [x] POST /api/users/{id}/projects (Director)
- [x] DELETE /api/users/{id}/projects/{pid} (Director)
- [x] GET /api/audit-log (Director, con filtros: project_id, actor_id, accion, desde, hasta)
- [x] GET /usuarios (Vista HTML, Director)
- [x] GET /usuarios/{id} (Vista HTML, Director)
- [x] GET /auditoria (Vista HTML, Director)

---

**Progreso Fase 8:** 95 / 95 funcionalidades

**Total CooperApp (Fases 1-8):** ~215-235 / ~215-235 funcionalidades
