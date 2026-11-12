# Design: Arquitectura de Datos y Lógica de Cálculo

## 1. Estructura de Datos Relacional y Tablero Dinámico
- **Entidades:** `Programmer`, `Sprint`, `Task`, `TaskAssignment`.
- **Desglose de Tareas y Asignación Flexible:**
  - Cada sprint agrupa un conjunto de tareas con su estado (`completed` o `in_progress`).
  - La relación `TaskAssignment` permite que una misma tarea tenga múltiples integrantes (trabajo en equipo) y que un integrante asuma múltiples tareas en un sprint (doble trabajo).
- **Esfuerzo Aportado por Sprint ($T_{sprint\_i}$):** Número de asignaciones de tareas completadas por el desarrollador en el sprint $i$.
- **Acumulado Histórico ($T_{acumulada}$):** 
  $$\text{Total Acumulado}_x = \sum_{i=1}^{N} T_{sprint\_i}$$
- **Total Global de Asignaciones del Equipo:**
  $$\text{Total Global} = \sum_{x \in \text{Miembros}} \text{Total Acumulado}_x$$

## 2. Indicadores Visuales y Porcentaje de Ingresos
- **Porcentaje de Participación de Ingresos:**
  $$\text{Porcentaje de Ingresos}_x = \left( \frac{\text{Total Acumulado}_x}{\text{Total Global}} \right) \times 100$$
- **Tasa de Avance Global (Círculo Principal):**
  $$\text{Tasa de Asignaciones Realizadas} = \left( \frac{\text{Total Asignaciones Completadas}}{\text{Total Asignaciones Planificadas}} \right) \times 100$$
- **Eficacia Individual (Círculos por Miembro):**
  $$\text{Eficacia}_x = \left( \frac{\text{Asignaciones Completadas}_x}{\text{Asignaciones Totales Asignadas}_x} \right) \times 100$$

