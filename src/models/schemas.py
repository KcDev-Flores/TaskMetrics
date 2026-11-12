from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Modelos de Dominio
# -----------------------------------------------------------------------------

@dataclass
class Programmer:
    name: str
    id: Optional[str] = None
    active: bool = True


@dataclass
class TaskItem:
    title: str
    status: str = "completed"  # 'completed' o 'in_progress'
    assigned_programmers: List[str] = field(default_factory=list)
    id: Optional[str] = None
    sprint_id: Optional[str] = None


@dataclass
class SprintDetail:
    sprint_number: int
    name: str
    status: str = "completed"
    tasks: List[TaskItem] = field(default_factory=list)
    id: Optional[str] = None


# Alias para compatibilidad
Sprint = SprintDetail


@dataclass
class ProgrammerMetric:
    programmer_name: str
    sprint_tasks: Dict[int, int] = field(default_factory=dict)
    total_accumulated: int = 0
    total_assigned: int = 0
    percentage: float = 0.0
    completion_rate: float = 100.0


@dataclass
class MetricsMatrix:
    sprints: List[int]
    sprint_names: Dict[int, str]
    programmer_metrics: List[ProgrammerMetric]
    team_total_tasks: int = 0
    team_total_assigned: int = 0
    overall_completion_rate: float = 0.0
    sprint_totals: Dict[int, int] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# Esquemas Pydantic para la API Web
# -----------------------------------------------------------------------------

class ProgrammerCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Nombre o alias del integrante")


class ProgrammerUpdate(BaseModel):
    old_name: str
    new_name: str
    active: Optional[bool] = True


class TaskInput(BaseModel):
    title: str = Field(..., min_length=1, description="Nombre de la tarea")
    status: str = Field(default="completed", description="'completed' o 'in_progress'")
    assigned_programmers: List[str] = Field(default_factory=list, description="Lista de nombres de integrantes asignados")


class SprintCreateRequest(BaseModel):
    sprint_number: int = Field(..., ge=1, description="Número de sprint")
    name: str = Field(..., min_length=1, description="Nombre del sprint (ej. Sprint 1 - Core Engine)")
    status: str = Field(default="completed", description="Estado del sprint")
    tasks: List[TaskInput] = Field(default_factory=list, description="Listado de tareas y sus asignaciones")


class SprintUpdateRequest(BaseModel):
    sprint_number: int
    name: str
    status: str = "completed"
    tasks: List[TaskInput] = Field(default_factory=list)


class UserCredentials(BaseModel):
    email: str = Field(..., description="Correo electrónico del usuario")
    password: str = Field(..., min_length=6, description="Contraseña (mínimo 6 caracteres)")


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Token de actualización")


class AuthResponse(BaseModel):
    status: str = "success"
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    user: dict


class UserCreateAdmin(BaseModel):
    email: str = Field(..., description="Correo electrónico del usuario")
    password: str = Field(..., min_length=6, description="Contraseña temporal inicial")
    name: str = Field(..., min_length=1, description="Nombre o alias del integrante")
    role: str = Field(default="lider", description="Rol del usuario ('admin' o 'lider')")


class UserUpdateAdmin(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None


