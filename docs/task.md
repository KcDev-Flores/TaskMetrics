# Task: Plan de Desarrollo del Módulo de Métricas SDDiC

- [x] **Fase 1: Configuración de Estructuras**
  - [x] Crear la estructura de datos o script base en Python (`task_metrics/models.py`, `schema.sql`) para almacenar programadores y sprints con soporte para Supabase.
  - [x] Diseñar la tabla de doble entrada (Programador vs. Sprints) en `task_metrics/service.py` con formato renderizable en Markdown y consola.
- [x] **Fase 2: Motor de Cálculo y Acumulados**
  - [x] Implementar la función de suma histórica de tareas por integrante (`MetricsCalculator.calculate_accumulated`).
  - [x] Desarrollar la fórmula matemática para el cálculo del porcentaje dinámico con precisión decimal exacta (`MetricsCalculator.calculate_percentage`).
- [x] **Fase 3: Pruebas y Validación**
  - [x] Simular un escenario de 4 sprints con variaciones en las tareas (como en el ejemplo donde un dev hace 8 en lugar de 10) para verificar la precisión del porcentaje (`simulate_sprints.py` y `tests/test_metrics.py`).
