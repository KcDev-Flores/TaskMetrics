-- ==============================================================================
-- Schema SQL para Supabase (TaskMetrics)
-- ==============================================================================
-- Se puede ejecutar completo en el SQL Editor tantas veces como haga falta:
-- crea lo que falte y migra una base anterior (sin áreas) sin borrar datos.
--
-- Modelo de acceso: el backend (FastAPI) es la única puerta de entrada y usa la
-- llave service_role. RLS queda activado y sin políticas, de modo que las llaves
-- públicas (anon / authenticated) no pueden leer ni escribir estas tablas.
-- ==============================================================================

-- 0. Perfiles de usuario: rol y área de cada cuenta de Supabase Auth
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'lider')) DEFAULT 'lider',
    area TEXT, -- NULL para el admin; obligatoria para un líder
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS area TEXT;

-- Versiones anteriores creaban el perfil con un trigger que tomaba el rol de los
-- metadatos editables por el usuario. Los perfiles los crea ahora solo el backend.
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS public.handle_new_user();

-- 1. Integrantes evaluados (pertenecen a un área)
CREATE TABLE IF NOT EXISTS programmers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    area TEXT NOT NULL DEFAULT 'general',
    name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);
ALTER TABLE programmers ADD COLUMN IF NOT EXISTS area TEXT NOT NULL DEFAULT 'general';
ALTER TABLE programmers DROP CONSTRAINT IF EXISTS programmers_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_programmers_area_name ON programmers (area, lower(name));

-- 2. Sprints (la numeración es independiente en cada área)
CREATE TABLE IF NOT EXISTS sprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    area TEXT NOT NULL DEFAULT 'general',
    sprint_number INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed', -- 'completed', 'in_progress', 'planned'
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);
ALTER TABLE sprints ADD COLUMN IF NOT EXISTS area TEXT NOT NULL DEFAULT 'general';
ALTER TABLE sprints DROP CONSTRAINT IF EXISTS sprints_sprint_number_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_sprints_area_number ON sprints (area, sprint_number);

-- 3. Tareas del sprint
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed', -- 'completed', 'in_progress'
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 4. Asignaciones (varios integrantes por tarea y varias tareas por integrante)
CREATE TABLE IF NOT EXISTS task_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    programmer_id UUID NOT NULL REFERENCES programmers(id) ON DELETE CASCADE,
    completed BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_task_programmer UNIQUE (task_id, programmer_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_sprint ON tasks(sprint_id);
CREATE INDEX IF NOT EXISTS idx_assignments_task ON task_assignments(task_id);
CREATE INDEX IF NOT EXISTS idx_assignments_programmer ON task_assignments(programmer_id);

-- ==============================================================================
-- Acceso: solo el backend (service_role)
-- ==============================================================================
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE programmers ENABLE ROW LEVEL SECURITY;
ALTER TABLE sprints ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_assignments ENABLE ROW LEVEL SECURITY;

-- Elimina las políticas de versiones anteriores, que daban acceso total a
-- cualquier usuario autenticado sin distinguir áreas.
DO $$
DECLARE
    policy RECORD;
BEGIN
    FOR policy IN
        SELECT policyname, tablename
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename IN ('user_profiles', 'programmers', 'sprints', 'tasks', 'task_assignments')
    LOOP
        EXECUTE format('DROP POLICY %I ON public.%I', policy.policyname, policy.tablename);
    END LOOP;
END $$;

REVOKE ALL ON user_profiles, programmers, sprints, tasks, task_assignments FROM anon, authenticated;
GRANT ALL ON user_profiles, programmers, sprints, tasks, task_assignments TO service_role;
