from enum import Enum
from app.models.user import Rol


class Permiso(str, Enum):
    proyecto_ver = "proyecto_ver"
    proyecto_crear = "proyecto_crear"
    proyecto_editar = "proyecto_editar"
    proyecto_eliminar = "proyecto_eliminar"
    presupuesto_ver = "presupuesto_ver"
    presupuesto_editar = "presupuesto_editar"
    gasto_ver = "gasto_ver"
    gasto_crear = "gasto_crear"
    gasto_editar = "gasto_editar"
    gasto_validar = "gasto_validar"
    gasto_justificar = "gasto_justificar"
    transferencia_ver = "transferencia_ver"
    transferencia_gestionar = "transferencia_gestionar"
    marco_ver = "marco_ver"
    marco_editar = "marco_editar"
    documento_ver = "documento_ver"
    documento_subir = "documento_subir"
    documento_sellar = "documento_sellar"
    informe_generar = "informe_generar"
    informe_descargar = "informe_descargar"
    usuarios_gestionar = "usuarios_gestionar"
    auditoria_ver = "auditoria_ver"
    aplazamiento_solicitar = "aplazamiento_solicitar"
    aplazamiento_aprobar = "aplazamiento_aprobar"


PERMISOS_POR_ROL: dict[Rol, set[Permiso]] = {
    Rol.director: set(Permiso),
    Rol.coordinador: {
        Permiso.proyecto_ver,
        Permiso.proyecto_crear,
        Permiso.proyecto_editar,
        Permiso.proyecto_eliminar,
        Permiso.presupuesto_ver,
        Permiso.presupuesto_editar,
        Permiso.gasto_ver,
        Permiso.gasto_crear,
        Permiso.gasto_editar,
        Permiso.gasto_validar,
        Permiso.gasto_justificar,
        Permiso.transferencia_ver,
        Permiso.transferencia_gestionar,
        Permiso.marco_ver,
        Permiso.marco_editar,
        Permiso.documento_ver,
        Permiso.documento_subir,
        Permiso.documento_sellar,
        Permiso.informe_generar,
        Permiso.informe_descargar,
        Permiso.aplazamiento_solicitar,
        Permiso.aplazamiento_aprobar,
    },
    Rol.tecnico_sede: {
        Permiso.proyecto_ver,
        Permiso.proyecto_editar,
        Permiso.presupuesto_ver,
        Permiso.presupuesto_editar,
        Permiso.gasto_ver,
        Permiso.gasto_crear,
        Permiso.gasto_editar,
        Permiso.gasto_validar,
        Permiso.gasto_justificar,
        Permiso.transferencia_ver,
        Permiso.transferencia_gestionar,
        Permiso.marco_ver,
        Permiso.marco_editar,
        Permiso.documento_ver,
        Permiso.documento_subir,
        Permiso.documento_sellar,
        Permiso.informe_generar,
        Permiso.informe_descargar,
        Permiso.aplazamiento_solicitar,
    },
    Rol.gestor_pais: {
        Permiso.proyecto_ver,
        Permiso.presupuesto_ver,
        Permiso.gasto_ver,
        Permiso.gasto_crear,
        Permiso.gasto_editar,
        Permiso.transferencia_ver,
        Permiso.marco_ver,
        Permiso.marco_editar,
        Permiso.documento_ver,
        Permiso.documento_subir,
        Permiso.informe_descargar,
    },
}


def user_has_permission(rol: Rol | None, permiso: Permiso) -> bool:
    if not rol:
        return False
    return permiso in PERMISOS_POR_ROL.get(rol, set())
