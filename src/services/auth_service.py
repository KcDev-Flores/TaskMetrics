"""
Autenticación y gestión de usuarios (roles: admin y líder de área).

- Con Supabase configurado, las cuentas viven en Supabase Auth y los perfiles en la
  tabla `user_profiles`. No hay respaldo local: si Supabase falla, el error se muestra.
- Sin Supabase (modo local de desarrollo) todo se guarda en SQLite.
"""

from typing import Any, Dict, List, Optional

from src.core.config import Config
from src.database.sqlite import SQLiteMetricsRepository

ROLES = ("admin", "lider")
MIN_PASSWORD_LENGTH = 6


class SupabaseAuthService:
    def __init__(self):
        self.is_configured = Config.is_supabase_configured()
        self.db: Any = None
        self._local: Optional[SQLiteMetricsRepository] = None

        if self.is_configured:
            from supabase import create_client

            # Cliente service_role: tablas y administración de cuentas. Nunca inicia
            # sesión con él, para que no adopte el token de un usuario.
            self.db = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)

    @property
    def local(self) -> SQLiteMetricsRepository:
        if self._local is None:
            self._local = SQLiteMetricsRepository()
        return self._local

    @staticmethod
    def _anon_client():
        """Cliente desechable para iniciar o refrescar sesión sin compartir estado."""
        from supabase import create_client

        return create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    # -------------------------------------------------------------------------
    # Perfiles
    # -------------------------------------------------------------------------
    def _get_profile(self, user_id: str) -> Optional[dict]:
        if self.is_configured:
            res = self.db.table("user_profiles").select("*").eq("id", user_id).limit(1).execute()
            return res.data[0] if res.data else None
        return self.local.get_user_profile(user_id)

    @staticmethod
    def _public_user(profile: dict) -> Dict[str, Any]:
        return {
            "id": str(profile["id"]),
            "email": profile["email"],
            "name": profile["name"],
            "role": profile["role"],
            "area": profile.get("area"),
            "active": bool(profile.get("active", True)),
        }

    def _require_usable_profile(self, user_id: str) -> dict:
        profile = self._get_profile(user_id)
        if not profile:
            raise ValueError("Tu cuenta no tiene un perfil asignado. Pide al administrador que te registre.")
        if not profile.get("active", True):
            raise ValueError("Tu cuenta ha sido desactivada por el administrador.")
        return profile

    @staticmethod
    def _normalize_role_and_area(role: str, area: Optional[str]) -> tuple:
        if role not in ROLES:
            raise ValueError("El rol debe ser 'admin' o 'lider'.")
        if role == "admin":
            return role, None
        clean_area = (area or "").strip().lower()
        if clean_area not in Config.AREAS:
            raise ValueError(f"Un líder necesita un área válida: {', '.join(Config.AREAS)}.")
        return role, clean_area

    # -------------------------------------------------------------------------
    # Sesión
    # -------------------------------------------------------------------------
    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        email = email.strip().lower()

        if self.is_configured:
            from supabase_auth.errors import AuthApiError

            try:
                res = self._anon_client().auth.sign_in_with_password({"email": email, "password": password})
            except AuthApiError as e:
                if "invalid login credentials" in str(e).lower():
                    raise ValueError("Correo o contraseña incorrectos.")
                raise ValueError(f"Supabase rechazó el inicio de sesión: {e}")
            if not res.session or not res.user:
                raise ValueError("Credenciales inválidas o cuenta no verificada.")

            profile = self._require_usable_profile(str(res.user.id))
            return self._session_payload(
                profile, res.session.access_token, res.session.refresh_token,
                getattr(res.session, "expires_in", 3600)
            )

        profile = self.local.verify_credentials(email, password)
        if not profile:
            raise ValueError("Correo o contraseña incorrectos.")
        if not profile["active"]:
            raise ValueError("Tu cuenta ha sido desactivada por el administrador.")
        return self._session_payload(
            profile,
            self.local.create_session(profile["id"], "access"),
            self.local.create_session(profile["id"], "refresh"),
            None
        )

    def _session_payload(self, profile: dict, access: str, refresh: Optional[str], expires_in: Optional[int]) -> Dict[str, Any]:
        return {
            "status": "success",
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": expires_in,
            "user": self._public_user(profile),
        }

    def get_user(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Valida el token y devuelve el usuario con su rol y área; None si no es válido."""
        if not access_token:
            return None
        token = access_token.replace("Bearer ", "").strip()

        if self.is_configured:
            from supabase_auth.errors import AuthApiError

            try:
                res = self.db.auth.get_user(token)
            except AuthApiError:
                return None
            if not res or not res.user:
                return None
            profile = self._get_profile(str(res.user.id))
        else:
            profile = self.local.get_session_profile(token, "access")

        if not profile or not profile.get("active", True):
            return None
        return {**self._public_user(profile), "token": token}

    def refresh_session(self, refresh_token: str) -> Dict[str, Any]:
        if self.is_configured:
            from supabase_auth.errors import AuthApiError

            try:
                res = self._anon_client().auth.refresh_session(refresh_token)
            except AuthApiError as e:
                raise ValueError(f"Token de actualización inválido: {e}")
            if not res.session or not res.user:
                raise ValueError("No se pudo refrescar la sesión.")
            profile = self._require_usable_profile(str(res.user.id))
            return self._session_payload(
                profile, res.session.access_token, res.session.refresh_token,
                getattr(res.session, "expires_in", 3600)
            )

        profile = self.local.get_session_profile(refresh_token, "refresh")
        if not profile or not profile["active"]:
            raise ValueError("Token de actualización inválido.")
        return self._session_payload(
            profile, self.local.create_session(profile["id"], "access"), refresh_token, None
        )

    def sign_out(self, access_token: Optional[str] = None) -> None:
        if not access_token:
            return
        if self.is_configured:
            from supabase_auth.errors import AuthApiError

            try:
                self.db.auth.admin.sign_out(access_token)
            except AuthApiError:
                pass
        else:
            self.local.delete_session(access_token)

    # -------------------------------------------------------------------------
    # Administración de usuarios (solo rol 'admin')
    # -------------------------------------------------------------------------
    def list_users(self) -> List[Dict[str, Any]]:
        if self.is_configured:
            res = self.db.table("user_profiles").select("*").order("name").execute()
            profiles = res.data or []
        else:
            profiles = self.local.list_user_profiles()
        return [{**self._public_user(p), "created_at": p.get("created_at")} for p in profiles]

    def create_user(self, email: str, password: str, name: str, role: str = "lider", area: Optional[str] = None) -> Dict[str, Any]:
        email = email.strip().lower()
        name = name.strip()
        if not email or "@" not in email:
            raise ValueError("Correo electrónico inválido.")
        if not name:
            raise ValueError("El nombre es obligatorio.")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"La contraseña debe tener mínimo {MIN_PASSWORD_LENGTH} caracteres.")
        role, area = self._normalize_role_and_area(role, area)

        if self.is_configured:
            from supabase_auth.errors import AuthApiError

            try:
                created = self.db.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"name": name},
                })
            except AuthApiError as e:
                if "already" in str(e).lower():
                    raise ValueError(f"Ya existe un usuario con el correo {email}.")
                raise ValueError(f"Supabase no pudo crear la cuenta: {e}")

            user_id = str(created.user.id)
            try:
                res = self.db.table("user_profiles").upsert({
                    "id": user_id,
                    "email": email,
                    "name": name,
                    "role": role,
                    "area": area,
                    "active": True,
                }).execute()
            except Exception:
                # Sin perfil la cuenta no puede entrar: no se deja a medias
                self.db.auth.admin.delete_user(user_id)
                raise
            profile = res.data[0]
        else:
            profile = self.local.create_user_profile(email, name, role, area, password)

        return {
            "status": "success",
            "message": f"Usuario '{name}' ({role}) creado exitosamente.",
            "user": self._public_user(profile),
        }

    def update_user(
        self,
        user_id: str,
        acting_user_id: str,
        name: Optional[str] = None,
        role: Optional[str] = None,
        area: Optional[str] = None,
        active: Optional[bool] = None,
        password: Optional[str] = None,
    ) -> bool:
        profile = self._get_profile(user_id)
        if not profile:
            return False

        changes: Dict[str, Any] = {}
        if name is not None:
            if not name.strip():
                raise ValueError("El nombre es obligatorio.")
            changes["name"] = name.strip()
        if role is not None or area is not None:
            new_role, new_area = self._normalize_role_and_area(
                role or profile["role"],
                area if area is not None else profile.get("area"),
            )
            changes["role"], changes["area"] = new_role, new_area
        if active is not None:
            changes["active"] = active
        if password:
            if len(password) < MIN_PASSWORD_LENGTH:
                raise ValueError(f"La contraseña debe tener mínimo {MIN_PASSWORD_LENGTH} caracteres.")

        if user_id == acting_user_id and (changes.get("role", "admin") != "admin" or changes.get("active") is False):
            raise ValueError("No puedes quitarte el rol de administrador ni desactivar tu propia cuenta.")

        if self.is_configured:
            if changes:
                self.db.table("user_profiles").update(changes).eq("id", user_id).execute()
            if password:
                from supabase_auth.errors import AuthApiError

                try:
                    self.db.auth.admin.update_user_by_id(user_id, {"password": password})
                except AuthApiError as e:
                    raise ValueError(f"Supabase no pudo cambiar la contraseña: {e}")
            return True

        if password:
            changes["password"] = password
        return self.local.update_user_profile(user_id, changes)

    def delete_user(self, user_id: str) -> bool:
        if not self._get_profile(user_id):
            return False
        if self.is_configured:
            from supabase_auth.errors import AuthApiError

            try:
                # El perfil se elimina en cascada (user_profiles.id -> auth.users.id)
                self.db.auth.admin.delete_user(user_id)
            except AuthApiError as e:
                if "not found" not in str(e).lower():
                    raise ValueError(f"Supabase no pudo eliminar la cuenta: {e}")
            self.db.table("user_profiles").delete().eq("id", user_id).execute()
            return True
        return self.local.delete_user_profile(user_id)
