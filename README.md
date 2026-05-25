# JobSearcher — Agente de Búsqueda de Empleo para Lyfter

Agente de IA que ayuda a estudiantes del programa **Lyfter** a encontrar oportunidades laborales relevantes y accionables, alineadas con su perfil real, restricciones y nivel de empleabilidad.

---

## Problema

Los estudiantes de Lyfter terminan su formación con habilidades técnicas concretas pero sin visibilidad sobre el mercado laboral: no saben qué roles buscar, qué ofertas son realistas para su nivel, ni cómo presentarse. Las búsquedas genéricas producen ruido, no oportunidades.

## Solución

Un agente que:

1. **Entiende el perfil del estudiante** — stack, seniority, restricciones, preferencias
2. **Busca y filtra ofertas** relevantes de múltiples fuentes
3. **Rankea oportunidades** según compatibilidad real (hard filters + nice-to-have)
4. **Genera acciones concretas** — cómo aplicar, qué preparar, qué adaptar en el CV

---

## Subtarea 1: Perfil del Estudiante

Define el contrato base del agente. Sin un perfil claro, la búsqueda y el ranking producen resultados genéricos.

**Artefactos:**

- [`docs/specs/student-profile-spec.md`](docs/specs/student-profile-spec.md) — Especificación del esquema de perfil
- [`docs/specs/match-rubric.md`](docs/specs/match-rubric.md) — Rúbrica de compatibilidad (hard filters vs. nice-to-have)
- [`fixtures/profiles/junior_frontend.json`](fixtures/profiles/junior_frontend.json) — Perfil de prueba: junior frontend
- [`fixtures/profiles/junior_fullstack.json`](fixtures/profiles/junior_fullstack.json) — Perfil de prueba: junior fullstack/backend

---

## Estructura del Proyecto

```
JobSearcher/
├── docs/
│   └── specs/
│       ├── student-profile-spec.md   # Spec de perfil + ejemplos
│       └── match-rubric.md           # Rúbrica de match
├── fixtures/
│   └── profiles/
│       ├── junior_frontend.json      # Perfil de prueba #1
│       └── junior_fullstack.json     # Perfil de prueba #2
└── README.md
```

_La arquitectura técnica (backend, frontend, integración con Ipsum) se definirá en una etapa posterior._

---

## Fuentes de Datos del Estudiante

Los datos del perfil se originan en el sistema **Ipsum** de Lyfter. Ver [`docs/specs/student-profile-spec.md`](docs/specs/student-profile-spec.md) para el mapeo completo de fuentes → campos del perfil.

---

## Contexto del Programa

**Lyfter** es un programa de aprendizaje que forma a estudiantes en desarrollo de software. Este agente es una herramienta interna para acelerar su inserción laboral al finalizar la formación.
