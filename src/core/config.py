import os
from typing import List, Optional
from dotenv import load_dotenv

# Carga variables de entorno de .env
load_dotenv()

DEFAULT_AREAS = "diseñador,blockbench,builder,doblaje"


class Config:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip()
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    PORT: int = int(os.getenv("PORT", 8000))
    HOST: str = os.getenv("HOST", "127.0.0.1")
    DEFAULT_PRECISION: int = int(os.getenv("METRICS_PRECISION", 4))
    STUDIO_NAME: str = os.getenv("STUDIO_NAME", "Café Estudio")
    AREAS: List[str] = [
        a.strip().lower() for a in os.getenv("AREAS", DEFAULT_AREAS).split(",") if a.strip()
    ]
    # Supabase Auth identifica las cuentas por correo: cada nombre de usuario se
    # registra allí como <usuario>@<este dominio>. Nadie recibe ni escribe ese correo.
    LOGIN_EMAIL_DOMAIN: str = os.getenv("LOGIN_EMAIL_DOMAIN", "usuarios.taskmetrics.local").strip().lower()
    # Solo modo local (sin Supabase)
    SQLITE_PATH: Optional[str] = os.getenv("TASKMETRICS_DB_PATH") or None
    LOCAL_ADMIN_USERNAME: str = os.getenv("LOCAL_ADMIN_USERNAME", "admin").strip().lower()
    LOCAL_ADMIN_PASSWORD: str = os.getenv("LOCAL_ADMIN_PASSWORD", "admin123")

    @classmethod
    def _has_real_url(cls) -> bool:
        return bool(cls.SUPABASE_URL) and "your-project-ref" not in cls.SUPABASE_URL

    @classmethod
    def is_supabase_configured(cls) -> bool:
        return cls._has_real_url() and bool(cls.SUPABASE_KEY) and bool(cls.SUPABASE_SERVICE_ROLE_KEY)

    @classmethod
    def missing_supabase_settings(cls) -> List[str]:
        """Variables que faltan cuando Supabase está configurado a medias."""
        if not cls._has_real_url():
            return []
        return [
            name
            for name in ("SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY")
            if not getattr(cls, name)
        ]
