import os
from dotenv import load_dotenv

# Carga variables de entorno de .env
load_dotenv()


class Config:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    PORT: int = int(os.getenv("PORT", 8000))
    HOST: str = os.getenv("HOST", "127.0.0.1")
    DEFAULT_PRECISION: int = int(os.getenv("METRICS_PRECISION", 4))

    @classmethod
    def is_supabase_configured(cls) -> bool:
        return bool(
            cls.SUPABASE_URL
            and cls.SUPABASE_KEY
            and "your-project-ref" not in cls.SUPABASE_URL
        )

