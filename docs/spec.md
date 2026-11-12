# Spec: Sistema de Registro y Ponderación de Ingresos por Sprint

## 1. Objetivo del Sistema
Definir los requerimientos para un sistema de control y cálculo que permita al líder de estudio registrar el rendimiento del equipo de programación sprint a sprint, asegurando una distribución de ingresos totalmente equitativa y transparente al finalizar el desarrollo del mod de Minecraft.

## 2. Requerimientos Funcionales
- **Definición de Sprints con Lista de Tareas:** Cada sprint se compone de su nombre/número y su listado de tareas específicas (ej. Tarea 1, Tarea 2, etc.).
- **Asignación Múltiple y Colaboración Compartida:** 
  - Una tarea puede estar asignada a múltiples desarrolladores si requirió trabajo en equipo (ej. Capo y Dreymor en Tarea 1).
  - Un desarrollador puede asumir múltiples tareas en un mismo sprint, reflejando su mayor aportación y esfuerzo real.
- **Sprints Dinámicos e Ilimitados:** La cantidad de sprints no es fija ($N \ge 1$); la matriz de doble entrada se expande dinámicamente con cada sprint registrado.
- **Menú de Acciones Centralizado (`Acciones`):** Botón desplegable jerárquico para Crear, Editar y Eliminar tanto Sprints como Integrantes.
- **Dashboard Visual con Indicadores Circulares:**
  - Círculo de porcentaje total de asignaciones realizadas del proyecto.
  - Círculos individuales de porcentaje de participación en ingresos y eficacia para cada integrante.
- **Persistencia No Volátil Garantizada:** Almacenamiento persistente en base de datos local y sincronizable con Supabase Cloud.
- **Cálculo Automático de Ingresos:** Recálculo exacto del porcentaje acumulado de ingresos sin errores de redondeo.

## 3. Permisos, Autonomía e Innovación del Agente
Para garantizar un flujo de desarrollo ágil y sin fricciones innecesarias, el agente operará bajo las siguientes directrices de autonomía:

- **Innovación y Proactividad:** El agente tiene total permiso para proponer, diseñar e implementar de iniciativa propia mejoras, estructuras o características adicionales que considere convenientes para optimizar el proyecto, sin necesidad de esperar una orden explícita para cada detalle menor.
- **Ejecución de Comandos de Baja Prioridad:** El agente está autorizado para ejecutar de forma autónoma comandos seguros de consulta y diagnóstico (como listar directorios, leer archivos de configuración, verificar rutas o comprobar estados locales) sin requerir autorización previa del líder, excluyendo estrictamente comandos de alto riesgo o que comprometan la seguridad del sistema.
- **Pausa Crítica y Retroalimentación:** El agente tiene el permiso y la obligación de detener su flujo de trabajo habitual si detecta ambigüedades, inconsistencias en el código, o si considera necesario aportar sugerencias, advertencias o recomendaciones técnicas antes de continuar con la ejecución de una tarea.