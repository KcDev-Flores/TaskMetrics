# TaskMetrics 🚀

**Sistema de Gestión de Sprints, Rendimiento y Ponderación de Ingresos**  
Desarrollado en Python con base de datos relacional persistente (SQLite local y [Supabase](https://supabase.com/) PostgreSQL en la nube).

---

## 🏛️ Estructura Limpia del Proyecto

El proyecto está organizado siguiendo principios de arquitectura limpia y modular:

```text
TaskMetrics/
├── docs/                      # 📑 Especificaciones, historias de usuario y diseño
│   ├── AGENT.md               # Directrices de auditoría y neutralidad matemática
│   ├── component.md           # Historias de usuario (HU-01, HU-02, HU-03)
│   ├── design.md              # Algoritmos de cálculo, colaboración y matrices dinámicas
│   ├── dictionary.md          # Glosario técnico
│   ├── spec.md                # Especificación de requerimientos y asignación múltiple
│   └── task.md                # Roadmap y fases de desarrollo
├── src/                       # 💻 Código fuente de la aplicación
│   ├── core/                  # Motor matemático puro y configuraciones
│   │   ├── calculator.py      # Precisión decimal exacta (sin errores de float)
│   │   └── config.py          # Variables de entorno y ajustes
│   ├── database/              # Capa de persistencia (No volátil)
│   │   ├── base.py            # Contrato abstracto del repositorio
│   │   ├── sqlite.py          # Persistencia local relacional en SQLite
│   │   └── supabase.py        # Conexión persistente PostgreSQL en Supabase
│   ├── models/                # Modelos de dominio y esquemas Pydantic
│   │   └── schemas.py
│   ├── services/              # Lógica de negocio y exportación (CSV / Markdown)
│   │   └── metrics_service.py
│   └── web/                   # Aplicación Web y Dashboard interactivo
│       ├── app.py             # FastAPI App y endpoints REST
│       ├── templates/         # HTML Dashboard con Tailwind CSS
│       │   └── index.html
│       └── static/            # Recursos estáticos
│           ├── css/styles.css
│           └── js/app.js      # Lógica frontend reactiva
├── tests/                     # 🧪 Suite de pruebas unitarias y de API
│   └── test_metrics.py
├── database/                  # 🗄️ Scripts SQL
│   └── schema.sql             # Tablas, tareas, asignaciones, llaves foráneas y RLS
├── .env.example               # Plantilla de credenciales Supabase
├── .gitignore                 # Exclusiones de Git
├── requirements.txt           # Dependencias de producción
├── run.py                     # 🌐 Servidor Web principal (FastAPI)
├── main.py                    # ⌨️ CLI para terminal
└── simulate_sprints.py        # 📊 Script de simulación con tareas compartidas
```

---

## ⚡ Inicio Rápido (Correr la Web)

### 1. Activar el entorno virtual e instalar dependencias
*(El entorno `.venv` ya está configurado en este repositorio)*

En **PowerShell**:
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Iniciar el Servidor Web
Ejecuta:
```powershell
python run.py
```
O directamente con el entorno virtual:
```powershell
.\.venv\Scripts\python run.py
```

Abre tu navegador en:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**  
👉 Documentación de la API: **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---

## 🖥️ Características del Dashboard

- **Menú Central `⚙️ Acciones ▾`:**
  - **Sprint:** Agregar nuevo sprint, editar sprint existente o eliminar sprint.
  - **Integrantes:** Agregar nuevo integrante, editar integrante o eliminar integrante.
- **Desglose de Tareas y Colaboración Compartida:**
  - Define tareas por sprint con su título y estado.
  - Asigna uno o múltiples desarrolladores a una misma tarea si trabajaron en equipo (ej. Capo y Dreymor en Motor Principal).
  - Permite que un integrante asuma múltiples tareas en un sprint (reflejando mayor esfuerzo y crédito).
- **Indicadores Circulares de Desempeño:**
  - **Círculo Global:** % total de asignaciones realizadas respecto a las planificadas.
  - **Círculos Individuales:** Muestran el % de participación en ingresos, tareas completadas y eficacia para cada miembro del equipo.
- **Tablero de Rendimiento (Matriz de Doble Entrada):**
  - Filas por integrante, columnas por sprint dinámico ($S_1, S_2, \dots, S_N$).
  - Total acumulado y porcentaje de ingresos con barra de progreso.
- **Detalle de Sprints (Acordeón):** Visualiza cada tarea, su estado y quién colaboró con quién.
- **Filtro Histórico:** Consulta el estado de ingresos en cualquier sprint pasado mediante *"Ver histórico hasta"*.
- **Exportación Directa:** Descarga el reporte actual en **CSV** o **Markdown**.

---

## 🔐 Supabase Auth y Rutas Protegidas

TaskMetrics implementa autenticación mediante **Supabase Auth** y protección a nivel de API y base de datos con **Row Level Security (RLS)**:

1. **Seguridad en Base de Datos (RLS):**
   - El archivo [`database/schema.sql`](file:///c:/Users/ADMIN/Documents/projects/GitHub%20Destkop/TaskMetrics/database/schema.sql) implementa políticas RLS mediante cláusulas `TO authenticated`.
   - Se revocan permisos de mutación al rol anónimo (`anon`) y se exige que todo usuario esté validado para leer, crear, actualizar o eliminar sprints, tareas e integrantes.
2. **Endpoints de Autenticación:**
   - `POST /api/auth/register`: Registro de nuevos usuarios en Supabase Auth.
   - `POST /api/auth/login`: Autenticación con email y contraseña, retornando `access_token` (JWT) y `refresh_token`.
   - `POST /api/auth/refresh`: Refresco de sesión para tokens expirados.
   - `POST /api/auth/logout`: Cierre de sesión.
   - `GET /api/auth/me`: Verificación de identidad y rol del usuario logueado.
3. **Rutas Protegidas:**
   - Todas las llamadas de lectura y escritura (`/api/metrics`, `/api/sprints`, `/api/programmers`, `/api/export`) requieren el header `Authorization: Bearer <token>`.
   - Las peticiones sin token o con token revocado devuelven automáticamente `401 Unauthorized`.
4. **Interfaz de Usuario Web:**
   - Barra superior con botón dinámico de **Iniciar Sesión** o badge de perfil (`usuario@correo.com`) con botón de cierre de sesión.
   - Modal reactivo con pestañas de *Iniciar Sesión* y *Crear Cuenta* con validación de credenciales.
   - Inyección automática de tokens JWT en todas las consultas asíncronas (`authFetch`).
   - Modo Dev / Offline: Si Supabase no está configurado en `.env`, el sistema permite autenticación local dev con credenciales de prueba (`admin@taskmetrics.com` / `admin123`) para desarrollo ágil sin conexión.

---

## ☁️ Conexión con Supabase en Producción

Por defecto, si no configuras `.env`, el sistema opera en modo local no volátil. Para conectar tu proyecto en la nube:

1. En tu proyecto de Supabase, entra a **SQL Editor**, copia el contenido de [`database/schema.sql`](file:///c:/Users/ADMIN/Documents/projects/GitHub%20Destkop/TaskMetrics/database/schema.sql) y pulsa **Run**.
2. Copia `.env.example` a `.env` y coloca tus credenciales:
   ```env
   SUPABASE_URL=https://<tu-proyecto>.supabase.co
   SUPABASE_KEY=<tu-anon-key>
   ```
3. Inicia la aplicación:
   ```powershell
   python run.py
   ```
4. Abre `http://127.0.0.1:8000/` y regístrate o inicia sesión con tu usuario de Supabase.

