-- ==============================================================================
-- Schema SQL para Supabase (TaskMetrics) - Modelo Relacional de Asignaciones
-- ==============================================================================

-- 0. Tabla de Perfiles de Usuario y Roles (Admin y Líder)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'lider')) DEFAULT 'lider',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Trigger para sincronizar automáticamente nuevos usuarios de auth.users a user_profiles
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email, name, role)
    VALUES (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
        coalesce(new.raw_user_meta_data->>'role', 'lider')
    )
    ON CONFLICT (id) DO UPDATE
    SET email = excluded.email;
    RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 1. Tabla de Programadores
CREATE TABLE IF NOT EXISTS programmers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 2. Tabla de Sprints
CREATE TABLE IF NOT EXISTS sprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_number INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed', -- 'completed', 'in_progress', 'planned'
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 3. Tabla de Tareas del Sprint
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sprint_id UUID NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed', -- 'completed', 'in_progress'
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 4. Tabla de Asignaciones (Permite múltiples desarrolladores por tarea y múltiples tareas por desarrollador)
CREATE TABLE IF NOT EXISTS task_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    programmer_id UUID NOT NULL REFERENCES programmers(id) ON DELETE CASCADE,
    completed BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_task_programmer UNIQUE (task_id, programmer_id)
);

-- Índices de consulta rápida
CREATE INDEX IF NOT EXISTS idx_tasks_sprint ON tasks(sprint_id);
CREATE INDEX IF NOT EXISTS idx_assignments_task ON task_assignments(task_id);
CREATE INDEX IF NOT EXISTS idx_assignments_programmer ON task_assignments(programmer_id);

-- ==============================================================================
-- Configuración de Permisos y Row Level Security (RLS) con Supabase Auth
-- ==============================================================================

-- 1. Habilitar RLS en todas las tablas
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE programmers ENABLE ROW LEVEL SECURITY;
ALTER TABLE sprints ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_assignments ENABLE ROW LEVEL SECURITY;

-- 2. Limpieza de políticas públicas anteriores inseguras
DROP POLICY IF EXISTS "Acceso publico user_profiles" ON user_profiles;
DROP POLICY IF EXISTS "Acceso publico programmers" ON programmers;
DROP POLICY IF EXISTS "Acceso publico sprints" ON sprints;
DROP POLICY IF EXISTS "Acceso publico tasks" ON tasks;
DROP POLICY IF EXISTS "Acceso publico task_assignments" ON task_assignments;

-- 3. Concesión de permisos para el rol 'authenticated' en el esquema público
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- Revocar permisos de escritura para el rol 'anon'
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM anon;

-- ------------------------------------------------------------------------------
-- 3.1. Políticas RLS para 'user_profiles' (Lectura para equipo, Mutación solo Admin)
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "user_profiles_select_auth" ON user_profiles;
CREATE POLICY "user_profiles_select_auth" ON user_profiles
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "user_profiles_admin_insert" ON user_profiles;
CREATE POLICY "user_profiles_admin_insert" ON user_profiles
    FOR INSERT TO authenticated WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE user_profiles.id = (SELECT auth.uid()) AND user_profiles.role = 'admin'
        )
    );

DROP POLICY IF EXISTS "user_profiles_admin_update" ON user_profiles;
CREATE POLICY "user_profiles_admin_update" ON user_profiles
    FOR UPDATE TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE user_profiles.id = (SELECT auth.uid()) AND user_profiles.role = 'admin'
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE user_profiles.id = (SELECT auth.uid()) AND user_profiles.role = 'admin'
        )
    );

DROP POLICY IF EXISTS "user_profiles_admin_delete" ON user_profiles;
CREATE POLICY "user_profiles_admin_delete" ON user_profiles
    FOR DELETE TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE user_profiles.id = (SELECT auth.uid()) AND user_profiles.role = 'admin'
        )
    );

-- ------------------------------------------------------------------------------
-- 4. Políticas RLS para 'programmers' (Exclusivo para usuarios autenticados)
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "programmers_select_auth" ON programmers;
CREATE POLICY "programmers_select_auth" ON programmers
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "programmers_insert_auth" ON programmers;
CREATE POLICY "programmers_insert_auth" ON programmers
    FOR INSERT TO authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "programmers_update_auth" ON programmers;
CREATE POLICY "programmers_update_auth" ON programmers
    FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "programmers_delete_auth" ON programmers;
CREATE POLICY "programmers_delete_auth" ON programmers
    FOR DELETE TO authenticated USING (true);

-- ------------------------------------------------------------------------------
-- 5. Políticas RLS para 'sprints' (Exclusivo para usuarios autenticados)
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "sprints_select_auth" ON sprints;
CREATE POLICY "sprints_select_auth" ON sprints
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "sprints_insert_auth" ON sprints;
CREATE POLICY "sprints_insert_auth" ON sprints
    FOR INSERT TO authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "sprints_update_auth" ON sprints;
CREATE POLICY "sprints_update_auth" ON sprints
    FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "sprints_delete_auth" ON sprints;
CREATE POLICY "sprints_delete_auth" ON sprints
    FOR DELETE TO authenticated USING (true);

-- ------------------------------------------------------------------------------
-- 6. Políticas RLS para 'tasks' (Exclusivo para usuarios autenticados)
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "tasks_select_auth" ON tasks;
CREATE POLICY "tasks_select_auth" ON tasks
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "tasks_insert_auth" ON tasks;
CREATE POLICY "tasks_insert_auth" ON tasks
    FOR INSERT TO authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "tasks_update_auth" ON tasks;
CREATE POLICY "tasks_update_auth" ON tasks
    FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "tasks_delete_auth" ON tasks;
CREATE POLICY "tasks_delete_auth" ON tasks
    FOR DELETE TO authenticated USING (true);

-- ------------------------------------------------------------------------------
-- 7. Políticas RLS para 'task_assignments' (Exclusivo para usuarios autenticados)
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "task_assignments_select_auth" ON task_assignments;
CREATE POLICY "task_assignments_select_auth" ON task_assignments
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "task_assignments_insert_auth" ON task_assignments;
CREATE POLICY "task_assignments_insert_auth" ON task_assignments
    FOR INSERT TO authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "task_assignments_update_auth" ON task_assignments;
CREATE POLICY "task_assignments_update_auth" ON task_assignments
    FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "task_assignments_delete_auth" ON task_assignments;
CREATE POLICY "task_assignments_delete_auth" ON task_assignments
    FOR DELETE TO authenticated USING (true);
