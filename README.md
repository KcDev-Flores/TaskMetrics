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
│   ├── test_auth.py           # Sesión, roles y aislamiento entre áreas
│   └── test_metrics.py
├── database/                  # 🗄️ Scripts SQL
│   └── schema.sql             # Tablas, áreas, migración y RLS (solo backend)
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
  - **Integrantes:** Agregar nuevo integrante, editar integrante o eliminar integrante (del área activa).
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

## 👥 Roles y Áreas

- **Admin:** es el único que crea, edita o elimina usuarios (pestaña **Usuarios**). Ve y edita todas las áreas con el selector **Área** de la cabecera.
- **Líder:** pertenece a un área (`diseñador`, `blockbench`, `builder`, `doblaje`; configurable con `AREAS`). Solo ve y evalúa a los integrantes y sprints de su área; el porcentaje de esfuerzo se calcula dentro de ella.
- No existe registro público: una cuenta sin perfil creado por el admin no puede entrar.
- Se entra con **nombre de usuario y contraseña**, sin correo (por ejemplo `admin.cafeestudio`).

Los integrantes y la numeración de sprints son independientes en cada área.

---

## 🔐 Autenticación y Acceso a Datos

- Las cuentas viven en **Supabase Auth**; el usuario, el rol y el área están en la tabla `user_profiles`. Como Supabase Auth identifica las cuentas por correo, cada usuario se registra allí como `<usuario>@<LOGIN_EMAIL_DOMAIN>`; ese correo interno nunca se escribe ni recibe mensajes.
- El backend FastAPI es la única puerta a los datos: valida el token en cada petición, aplica el área del usuario y accede a Supabase con la llave `service_role`.
- [`database/schema.sql`](database/schema.sql) activa RLS sin políticas, así que las llaves públicas (`anon` / `authenticated`) no pueden leer ni escribir las tablas directamente.
- Endpoints de sesión: `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `GET /api/auth/me`. La interfaz renueva el token de acceso automáticamente cuando caduca.
- Todas las rutas de datos (`/api/metrics`, `/api/sprints`, `/api/programmers`, `/api/export`) exigen `Authorization: Bearer <token>`; el admin añade `?area=<área>`.
- **Modo local (sin Supabase):** si faltan las variables de Supabase, los datos y usuarios se guardan en SQLite (`database/taskmetrics.db`) con un admin inicial (`LOCAL_ADMIN_USERNAME` / `LOCAL_ADMIN_PASSWORD`, por defecto `admin` / `admin123`). Es solo para desarrollo: no lo despliegues así.

---

## ☁️ Conexión con Supabase

1. En tu proyecto de Supabase abre **SQL Editor**, pega el contenido de [`database/schema.sql`](database/schema.sql) y pulsa **Run**. Se puede volver a ejecutar sin perder datos; también migra una base creada con una versión anterior.
2. Define las tres variables de entorno (en un archivo `.env` en local, o en el panel del proveedor al desplegar):
   ```env
   SUPABASE_URL=https://<tu-proyecto>.supabase.co
   SUPABASE_KEY=<llave anon o publishable>
   SUPABASE_SERVICE_ROLE_KEY=<llave service_role o secret>
   ```
   Si defines `SUPABASE_URL` pero falta alguna de las llaves, la aplicación no arranca y lo indica en el log.
3. Crea el primer administrador (después podrás crear al resto desde la web):
   ```powershell
   python main.py create-user admin.cafeestudio "Tu Nombre" --role admin
   ```
4. Inicia la aplicación con `python run.py` y entra con esa cuenta.

### Despliegue (p. ej. Render)

- Despliega la rama que contiene esta versión y usa `pip install -r requirements.txt` como build y `python run.py` como comando de inicio.
- Variables: las tres de Supabase y `HOST=0.0.0.0`. `PORT` lo asigna el proveedor.
- Para comprobarlo abre `/api/auth/status`: debe responder `"supabase_configured": true`.

Variables opcionales:

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `STUDIO_NAME` | `Café Estudio` | Nombre que se muestra en la interfaz |
| `AREAS` | `diseñador,blockbench,builder,doblaje` | Áreas que se pueden asignar a un líder |
| `LOGIN_EMAIL_DOMAIN` | `usuarios.taskmetrics.local` | Dominio del correo interno de cada cuenta. No lo cambies con cuentas ya creadas: dejarían de poder entrar |
| `METRICS_PRECISION` | `4` | Decimales de los porcentajes |
| `LOCAL_ADMIN_USERNAME` / `LOCAL_ADMIN_PASSWORD` | `admin` / `admin123` | Admin inicial del modo local |

Recomendado: en Supabase → **Authentication → Sign In / Providers** desactiva *Allow new users to sign up* (las cuentas las crea el admin).

## 🧪 Pruebas

```powershell
pip install pytest httpx
python -m pytest
```

Las pruebas usan siempre una base SQLite temporal; nunca tocan Supabase.
