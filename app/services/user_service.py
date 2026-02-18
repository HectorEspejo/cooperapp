from datetime import datetime
from sqlalchemy.orm import Session
from app.models.user import User, Rol, user_project
from app.models.project import Project


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_from_entra(self, oid: str, email: str, nombre: str, apellidos: str) -> User:
        user = self.db.query(User).filter(User.entra_oid == oid).first()
        if user:
            user.email = email
            user.nombre = nombre
            user.apellidos = apellidos
            user.ultimo_acceso = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
            return user

        # Check by email
        user = self.db.query(User).filter(User.email == email).first()
        if user:
            user.entra_oid = oid
            user.nombre = nombre
            user.apellidos = apellidos
            user.ultimo_acceso = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
            return user

        user = User(
            email=email,
            nombre=nombre,
            apellidos=apellidos,
            entra_oid=oid,
            ultimo_acceso=datetime.utcnow(),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_or_create_dev_user(self) -> User:
        user = self.db.query(User).filter(User.email == "dev@cooperapp.local").first()
        if user:
            user.ultimo_acceso = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
            return user

        user = User(
            email="dev@cooperapp.local",
            nombre="Desarrollador",
            apellidos="CooperApp",
            entra_oid="dev-local",
            rol=Rol.director,
            ultimo_acceso=datetime.utcnow(),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_or_create_dev_user_with_role(self, rol: Rol) -> User:
        role_config = {
            Rol.director: ("director@cooperapp.local", "Ana", "Garcia (Director)", "dev-director"),
            Rol.coordinador: ("coordinador@cooperapp.local", "Carlos", "Lopez (Coordinador)", "dev-coordinador"),
            Rol.tecnico_sede: ("tecnico@cooperapp.local", "Maria", "Fernandez (Tecnico)", "dev-tecnico"),
            Rol.gestor_pais: ("gestor@cooperapp.local", "Pedro", "Martinez (Gestor)", "dev-gestor"),
        }
        email, nombre, apellidos, oid = role_config[rol]

        user = self.db.query(User).filter(User.email == email).first()
        if user:
            user.rol = rol
            user.ultimo_acceso = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
            return user

        user = User(
            email=email,
            nombre=nombre,
            apellidos=apellidos,
            entra_oid=oid,
            rol=rol,
            ultimo_acceso=datetime.utcnow(),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_all(self, rol: Rol | None = None, activo: bool | None = None, search: str | None = None) -> list[User]:
        query = self.db.query(User)
        if rol:
            query = query.filter(User.rol == rol)
        if activo is not None:
            query = query.filter(User.activo == activo)
        if search:
            query = query.filter(
                (User.nombre.ilike(f"%{search}%")) |
                (User.apellidos.ilike(f"%{search}%")) |
                (User.email.ilike(f"%{search}%"))
            )
        return query.order_by(User.created_at.desc()).all()

    def update_role(self, user_id: str, rol: Rol | None) -> User | None:
        user = self.get_by_id(user_id)
        if not user:
            return None
        user.rol = rol
        self.db.commit()
        self.db.refresh(user)
        return user

    def toggle_active(self, user_id: str) -> User | None:
        user = self.get_by_id(user_id)
        if not user:
            return None
        user.activo = not user.activo
        self.db.commit()
        self.db.refresh(user)
        return user

    def assign_project(self, user_id: str, project_id: int) -> bool:
        existing = self.db.execute(
            user_project.select().where(
                user_project.c.user_id == user_id,
                user_project.c.project_id == project_id,
            )
        ).first()
        if existing:
            return False
        self.db.execute(user_project.insert().values(user_id=user_id, project_id=project_id))
        self.db.commit()
        return True

    def unassign_project(self, user_id: str, project_id: int) -> bool:
        result = self.db.execute(
            user_project.delete().where(
                user_project.c.user_id == user_id,
                user_project.c.project_id == project_id,
            )
        )
        self.db.commit()
        return result.rowcount > 0

    def get_assigned_projects(self, user_id: str) -> list[Project]:
        user = self.get_by_id(user_id)
        if not user:
            return []
        return user.assigned_projects
