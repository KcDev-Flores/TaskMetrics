"""
FastAPI Security Dependencies para Supabase Auth
"""

from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.services.auth_service import SupabaseAuthService

# Instancia global del servicio de autenticación
auth_service = SupabaseAuthService()

# Extractor de Bearer Token de FastAPI (sin auto_error para permitir fallback a cookies si es necesario)
security_scheme = HTTPBearer(auto_error=False)


def get_token_from_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> Optional[str]:
    """Extrae el token Bearer del header Authorization o alternativamente de cookies."""
    if credentials and credentials.credentials:
        return credentials.credentials

    # Fallback opcional a cookie 'access_token'
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> Dict[str, Any]:
    """
    Dependencia de FastAPI para proteger rutas.
    Verifica el JWT con Supabase Auth.
    Lanza 401 si no está autenticado o el token es inválido.
    """
    token = get_token_from_request(request, credentials)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado: Falta el token de autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_service.get_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado: Token de Supabase no válido o sesión expirada.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> Optional[Dict[str, Any]]:
    """
    Dependencia para rutas públicas o mixtas que pueden beneficiarse
    de saber si hay un usuario logueado sin rechazar peticiones anónimas.
    """
    token = get_token_from_request(request, credentials)
    if not token:
        return None
    return auth_service.get_user(token)


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Verifica que el usuario actual tenga rol de 'admin'.
    Lanza 403 Forbidden si el rol es 'lider' o inferior.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: Solo el Administrador tiene autorización para esta acción."
        )
    return current_user


