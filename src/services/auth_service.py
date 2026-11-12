"""
Supabase Authentication Service con Soporte RBAC (Roles: Admin y Líder)
Manejo de registro, inicio de sesión, sesiones activas, perfiles y gestión administrativa de usuarios.
"""

import os
from typing import Any, Dict, List, Optional
from uuid import uuid4
from src.core.config import Config
from src.database.sqlite import SQLiteMetricsRepository


class SupabaseAuthService:
    """
    Servicio de autenticación integrado con Supabase Auth y perfiles de usuario.
    Permite acceso como Administrador (gestión total de usuarios) o Líder (gestión de sprints y tareas).
    """

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = url or Config.SUPABASE_URL
        self.key = key or Config.SUPABASE_KEY
        self.is_configured = Config.is_supabase_configured()
        self._client = None
        self._admin_client = None
        self._sqlite = SQLiteMetricsRepository()

        if self.is_configured:
            try:
                from supabase import create_client
                self._client = create_client(self.url, self.key)
                if Config.SUPABASE_SERVICE_ROLE_KEY:
                    self._admin_client = create_client(self.url, Config.SUPABASE_SERVICE_ROLE_KEY)
            except Exception:
                self._client = None
                self._admin_client = None
                self.is_configured = False

    def sign_up(self, email: str, password: str) -> Dict[str, Any]:
        """Registro público o estándar de usuario (asignado por defecto con rol 'lider')."""
        return self.create_user_by_admin(
            email=email,
            password=password,
            name=email.split("@")[0].capitalize(),
            role="lider"
        )


    def _get_or_create_profile(self, user_id: str, email: str, name: Optional[str] = None, role: Optional[str] = None) -> Dict[str, Any]:
        """Obtiene o inicializa el perfil de usuario con su rol correspondiente."""
        clean_email = email.strip().lower()
        clean_name = name or clean_email.split("@")[0].capitalize()

        if self._client and self.is_configured:
            try:
                res = self._client.table("user_profiles").select("*").eq("id", user_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]

                # Si es el primer usuario del sistema o correo admin, se le da rol 'admin'
                all_res = self._client.table("user_profiles").select("id").execute()
                assigned_role = role or ("admin" if (not all_res.data or "admin" in clean_email) else "lider")

                insert_res = self._client.table("user_profiles").insert({
                    "id": user_id,
                    "email": clean_email,
                    "name": clean_name,
                    "role": assigned_role,
                    "active": True
                }).execute()

                if insert_res.data and len(insert_res.data) > 0:
                    return insert_res.data[0]
            except Exception:
                pass

        # Fallback en SQLite
        existing = self._sqlite.get_user_profile(user_id) or self._sqlite.get_user_profile(clean_email)
        if existing:
            return existing

        all_profiles = self._sqlite.list_user_profiles()
        assigned_role = role or ("admin" if (not all_profiles or "admin" in clean_email) else "lider")
        return self._sqlite.upsert_user_profile(
            user_id=user_id,
            email=clean_email,
            name=clean_name,
            role=assigned_role,
            active=True
        )

    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Inicia sesión con email y contraseña, retornando el token y el perfil con rol."""
        email = email.strip().lower()

        if self._client and self.is_configured:
            try:
                res = self._client.auth.sign_in_with_password({"email": email, "password": password})
                if not res.session or not res.user:
                    raise ValueError("Credenciales inválidas o cuenta no verificada.")

                profile = self._get_or_create_profile(
                    user_id=str(res.user.id),
                    email=res.user.email,
                    name=res.user.user_metadata.get("name") if res.user.user_metadata else None
                )

                if not profile.get("active", True):
                    raise ValueError("Tu cuenta ha sido desactivada por el administrador.")

                return {
                    "status": "success",
                    "access_token": res.session.access_token,
                    "refresh_token": res.session.refresh_token,
                    "token_type": "bearer",
                    "expires_in": getattr(res.session, "expires_in", 3600),
                    "user": {
                        "id": str(res.user.id),
                        "email": res.user.email,
                        "name": profile.get("name", email.split("@")[0].capitalize()),
                        "role": profile.get("role", "lider"),
                        "active": profile.get("active", True),
                    }
                }
            except Exception as e:
                msg = str(e)
                if "invalid login credentials" in msg.lower() or "invalid_grant" in msg.lower():
                    raise ValueError("Correo o contraseña incorrectos.")
                raise ValueError(msg)
        else:
            # Modo Dev Offline persistido en SQLite
            profile = self._sqlite.get_user_profile(email)
            if not profile:
                # Comprobar si es admin por defecto
                if email == "admin@taskmetrics.com" and password == "admin123":
                    profile = self._sqlite.upsert_user_profile(
                        user_id=str(uuid4()),
                        email=email,
                        name="Administrador Principal",
                        role="admin",
                        password=password,
                        active=True
                    )
                elif email == "dev@taskmetrics.com" and password == "password123":
                    profile = self._sqlite.upsert_user_profile(
                        user_id=str(uuid4()),
                        email=email,
                        name="Líder Desarrollador",
                        role="lider",
                        password=password,
                        active=True
                    )
                else:
                    raise ValueError("Credenciales incorrectas.")

            if not profile.get("active", True):
                raise ValueError("Tu cuenta ha sido desactivada por el administrador.")

            mock_token = f"dev-token-{email}"
            return {
                "status": "success",
                "access_token": mock_token,
                "refresh_token": f"dev-refresh-{email}",
                "token_type": "bearer",
                "expires_in": 86400,
                "user": {
                    "id": str(profile["id"]),
                    "email": profile["email"],
                    "name": profile["name"],
                    "role": profile["role"],
                    "active": bool(profile["active"]),
                }
            }

    def get_user(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Valida el JWT y retorna la identidad del usuario junto con su rol ('admin' o 'lider')."""
        if not access_token:
            return None

        clean_token = access_token.replace("Bearer ", "").strip()

        if self._client and self.is_configured:
            try:
                res = self._client.auth.get_user(clean_token)
                if res and res.user:
                    profile = self._get_or_create_profile(
                        user_id=str(res.user.id),
                        email=res.user.email
                    )
                    return {
                        "id": str(res.user.id),
                        "email": res.user.email,
                        "name": profile.get("name", res.user.email.split("@")[0].capitalize()),
                        "role": profile.get("role", "lider"),
                        "active": profile.get("active", True),
                        "token": clean_token,
                    }
                return None
            except Exception:
                return None
        else:
            if clean_token.startswith("dev-token-"):
                email = clean_token.replace("dev-token-", "")
                profile = self._sqlite.get_user_profile(email)
                if profile:
                    return {
                        "id": str(profile["id"]),
                        "email": profile["email"],
                        "name": profile["name"],
                        "role": profile["role"],
                        "active": bool(profile["active"]),
                        "token": clean_token,
                    }
                return {
                    "id": f"dev-{hash(email) & 0xffffffff}",
                    "email": email,
                    "name": email.split("@")[0].capitalize(),
                    "role": "admin" if "admin" in email else "lider",
                    "active": True,
                    "token": clean_token,
                }
            return None

    def refresh_session(self, refresh_token: str) -> Dict[str, Any]:
        """Refresca la sesión."""
        if self._client and self.is_configured:
            try:
                res = self._client.auth.refresh_session(refresh_token)
                if not res.session or not res.user:
                    raise ValueError("No se pudo refrescar la sesión.")

                profile = self._get_or_create_profile(str(res.user.id), res.user.email)
                return {
                    "status": "success",
                    "access_token": res.session.access_token,
                    "refresh_token": res.session.refresh_token,
                    "token_type": "bearer",
                    "expires_in": getattr(res.session, "expires_in", 3600),
                    "user": {
                        "id": str(res.user.id),
                        "email": res.user.email,
                        "name": profile.get("name"),
                        "role": profile.get("role", "lider"),
                        "active": profile.get("active", True),
                    }
                }
            except Exception as e:
                raise ValueError(f"Token de actualización inválido: {e}")
        else:
            if refresh_token.startswith("dev-refresh-"):
                email = refresh_token.replace("dev-refresh-", "")
                profile = self._sqlite.get_user_profile(email) or {"name": email.split("@")[0].capitalize(), "role": "admin" if "admin" in email else "lider"}
                return {
                    "status": "success",
                    "access_token": f"dev-token-{email}",
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "expires_in": 86400,
                    "user": {
                        "id": f"dev-{hash(email) & 0xffffffff}",
                        "email": email,
                        "name": profile.get("name"),
                        "role": profile.get("role", "lider"),
                        "active": True,
                    }
                }
            raise ValueError("Refresh token inválido.")

    def sign_out(self, access_token: Optional[str] = None) -> None:
        """Cierra la sesión."""
        if self._client and self.is_configured:
            try:
                self._client.auth.sign_out()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Métodos Administrativos (Exclusivos para rol 'admin')
    # -------------------------------------------------------------------------
    def list_users(self) -> List[Dict[str, Any]]:
        """Lista todos los perfiles de usuario del sistema."""
        if self._client and self.is_configured:
            try:
                res = self._client.table("user_profiles").select("*").order("name").execute()
                if res.data:
                    return res.data
            except Exception:
                pass
        return self._sqlite.list_user_profiles()

    def create_user_by_admin(self, email: str, password: str, name: str, role: str = "lider") -> Dict[str, Any]:
        """Crea un nuevo usuario con rol específico ('admin' o 'lider') y lo habilita en el equipo."""
        email = email.strip().lower()
        name = name.strip()
        role = "admin" if role == "admin" else "lider"

        if len(password) < 6:
            raise ValueError("La contraseña debe tener mínimo 6 caracteres.")

        new_user_id = str(uuid4())

        if self._admin_client:
            try:
                # 1. Crear en Supabase Auth con email confirmado
                auth_res = self._admin_client.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"name": name, "role": role}
                })
                if auth_res.user:
                    new_user_id = str(auth_res.user.id)

                # 2. Registrar en user_profiles si existe la tabla
                try:
                    self._admin_client.table("user_profiles").upsert({
                        "id": new_user_id,
                        "email": email,
                        "name": name,
                        "role": role,
                        "active": True
                    }).execute()
                except Exception:
                    pass
            except Exception as e:
                msg = str(e)
                if "already registered" not in msg.lower() and "already exists" not in msg.lower():
                    pass
        elif self._client and self.is_configured:
            try:
                # 1. Crear en Supabase Auth
                auth_res = self._client.auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {"data": {"name": name, "role": role}}
                })
                if auth_res.user:
                    new_user_id = str(auth_res.user.id)

                # 2. Registrar o actualizar en user_profiles
                try:
                    self._client.table("user_profiles").upsert({
                        "id": new_user_id,
                        "email": email,
                        "name": name,
                        "role": role,
                        "active": True
                    }).execute()
                except Exception:
                    pass
            except Exception as e:
                pass

        # Guardar también en SQLite para coherencia local
        profile = self._sqlite.upsert_user_profile(
            user_id=new_user_id,
            email=email,
            name=name,
            role=role,
            password=password,
            active=True
        )

        return {
            "status": "success",
            "message": f"Usuario '{name}' ({role}) creado exitosamente.",
            "user": profile
        }

    def update_user_by_admin(
        self,
        user_id: str,
        name: Optional[str] = None,
        role: Optional[str] = None,
        active: Optional[bool] = None,
        password: Optional[str] = None
    ) -> bool:
        """Actualiza el nombre, rol o estado activo de un usuario."""
        if role is not None and role not in ["admin", "lider"]:
            raise ValueError("El rol debe ser 'admin' o 'lider'.")

        updated = False

        if self._client and self.is_configured:
            try:
                update_data = {}
                if name is not None:
                    update_data["name"] = name.strip()
                if role is not None:
                    update_data["role"] = role
                if active is not None:
                    update_data["active"] = active

                if update_data:
                    self._client.table("user_profiles").update(update_data).eq("id", user_id).execute()
                    updated = True
            except Exception:
                pass

        sqlite_ok = self._sqlite.update_user_profile(
            user_id=user_id,
            name=name,
            role=role,
            active=active,
            password=password
        )

        return updated or sqlite_ok

    def delete_user_by_admin(self, user_id: str) -> bool:
        """Elimina o desactiva a un usuario del sistema."""
        deleted = False
        if self._client and self.is_configured:
            try:
                self._client.table("user_profiles").delete().eq("id", user_id).execute()
                deleted = True
            except Exception:
                pass

        sqlite_ok = self._sqlite.delete_user_profile(user_id)
        return deleted or sqlite_ok
