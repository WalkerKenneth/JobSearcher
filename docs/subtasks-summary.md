# Resumen de Subtareas — JobSearcher

Repositorio: [WalkerKenneth/JobSearcher](https://github.com/WalkerKenneth/JobSearcher)

---

## Subtarea 1 — Definir perfil del candidato y criterios de match

**Estado:** ✅ Completado

**Qué se hizo:**
Se definió el contrato de datos para el perfil de estudiante (`StudentProfile`) y el modelo de evaluación de compatibilidad entre perfil y oferta laboral.

**Entregables:**

| Archivo | Descripción |
|---|---|
| [`docs/specs/student-profile-spec.md`](https://github.com/WalkerKenneth/JobSearcher/blob/main/docs/specs/student-profile-spec.md) | Schema completo del perfil: stack, idiomas, disponibilidad, salario esperado, restricciones y preferencias |
| [`docs/specs/match-rubric.md`](https://github.com/WalkerKenneth/JobSearcher/blob/main/docs/specs/match-rubric.md) | Filtros duros y rúbrica de scoring (0–100 pts) por componente |
| [`fixtures/profiles/junior_frontend.json`](https://github.com/WalkerKenneth/JobSearcher/blob/main/fixtures/profiles/junior_frontend.json) | Fixture de prueba: Valentina (frontend, Costa Rica) |
| [`fixtures/profiles/junior_fullstack.json`](https://github.com/WalkerKenneth/JobSearcher/blob/main/fixtures/profiles/junior_fullstack.json) | Fixture de prueba: Andrés (fullstack, Costa Rica) |

**Conclusiones y decisiones:**

- La evaluación de ofertas se diseñó en 2 fases secuenciales: **filtros duros** (binario — pasa o no pasa) y **scoring** (0–100). Una oferta que no pasa los filtros duros no se muestra al estudiante, sin importar su score.
- Los filtros duros eliminan por: salario máximo de la oferta por debajo del mínimo del perfil, modalidad excluida, ubicación excluida, sin visa sponsorship cuando el perfil la requiere, o porcentaje de viaje excesivo.
- El score se compone de 6 criterios ponderados: stack técnico (35 pts), seniority (20 pts), idioma (15 pts), sector preferido (15 pts), tamaño de empresa (10 pts) y título del rol (5 pts).
- Se definieron penalizaciones no eliminatorias: –20 pts por sector en `avoid_sectors`, –10 pts por salario bajo el rango esperado pero sobre el mínimo, –15 pts por tecnología crítica ausente.
- El campo `growth_priority` redistribuye los pesos del score según la prioridad del estudiante (`learning`, `salary`, `stability`, `impact`).
- La clasificación final determina la acción sugerida: 80–100 = aplicar de inmediato; 60–79 = aplicar con adaptaciones; 40–59 = revisar gaps; <40 = fuera de rango.

---

## Subtarea 2 — Spike de soluciones existentes para búsqueda de empleo

**Estado:** ✅ Completado

**Qué se hizo:**
Se evaluaron herramientas, APIs y scraping libraries existentes para obtener ofertas laborales, con foco en cobertura de Costa Rica y LATAM.

**Entregables:**

| Archivo | Descripción |
|---|---|
| [`docs/spikes/job-search-tools-spike.md`](https://github.com/WalkerKenneth/JobSearcher/blob/main/docs/spikes/job-search-tools-spike.md) | Evaluación comparativa: JSearch, SerpAPI, Adzuna, JobSpy, Apify |

**Conclusiones y decisiones:**

- **JSearch seleccionado para MVP:** free tier sin tarjeta de crédito (200 req/mes), integración mínima (1 endpoint REST), cobertura Costa Rica vía Google for Jobs (indexa Computrabajo CR, LinkedIn CR, Indeed CR). Upgrade path directo a Pro a $25/mes cuando el cohort crezca.
- **SerpAPI seleccionado para escala:** mejor cobertura LATAM, campo `job_highlights.Qualifications` semiestructurado que facilita extracción de stack sin NLP pesado, targeting por país (`gl`) e idioma (`hl=es`). $75/mes = 5,000 búsquedas mensuales.
- **JobSpy descartado definitivamente:** viola expresamente los ToS de LinkedIn, Indeed y Glassdoor. No apto para producción.
- **Adzuna descartado:** Costa Rica no es un país soportado — resultados nulos para el target principal.
- **Apify descartado:** dependencia de actor de terceros en marketplace (puede romperse o desaparecer) y LinkedIn sigue siendo ToS-risky.
- **Limitación transversal identificada:** el salario está ausente en el 70–85% de las ofertas de Costa Rica y LATAM en todas las fuentes. La rúbrica de `min_salary` solo aplica cuando el dato existe.

---

## Subtarea 3 — Evaluar OpenClaw vs Hermes para orquestación del agente

**Estado:** ✅ Completado

**Qué se hizo:**
Se evaluaron dos frameworks de orquestación de agentes (OpenClaw y Hermes) frente a una solución directa con Claude API + FastAPI. Se documentó la decisión como ADR. Hermes fue seleccionado como la capa de orquestación del pipeline.

**Entregables:**

| Archivo | Descripción |
|---|---|
| [`docs/decisions/adr-001-orchestration.md`](https://github.com/WalkerKenneth/JobSearcher/blob/main/docs/decisions/adr-001-orchestration.md) | ADR-001: decisión de arquitectura de orquestación |
| [`docs/spikes/orchestration-minimal-flow/minimal_flow.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/docs/spikes/orchestration-minimal-flow/minimal_flow.py) | Proof-of-concept del flujo mínimo con Claude API |

**Conclusiones y decisiones:**

- **Opción elegida: Hermes (orquestación por eventos + colas async con Redis).** El pipeline de JobSearcher tiene pasos claramente delimitados — cada uno (QueryBuilder, Fetcher, Normalizer, Scorer, Delivery) se implementa como un handler independiente de Hermes, permitiendo retries granulares y procesamiento concurrente de múltiples estudiantes.
- **OpenClaw descartado:** diseñado para sistemas multi-agente con decisiones no determinísticas. Para un pipeline lineal de pasos bien definidos, el overhead de mantener la plataforma supera los beneficios.
- **Claude API + FastAPI (sin orquestador) descartado como solución final:** si bien es la opción más simple para un script individual, el procesamiento sincrónico no escala a múltiples estudiantes concurrentes sin refactoring significativo.
- **Regla de arquitectura establecida:** el backend (workers Hermes, lógica determinística y testeable) maneja todo el pipeline; el LLM solo se llama en 2 puntos: `ExtractJobSignals` (stack + seniority de texto libre) y `GenerateAction` (acción personalizada por match). Si se puede hacer con `if/else` o regex, no se involucra al LLM.
- **Riesgos de seguridad documentados:** el agente nunca construye queries a APIs externas directamente (riesgo de inyección de parámetros), no tiene acceso a scraping genérico, y los workers reciben solo los campos mínimos del perfil necesarios por paso para proteger datos personales. Las credenciales de JSearch/SerpAPI viven exclusivamente en los workers.
- **Infraestructura:** Redis como broker; los workers de Hermes se despliegan junto al backend FastAPI (productor de solicitudes). El retry nativo de Hermes reemplaza el uso de `tenacity` en el `JobFetcher`.

---

## Subtarea 4 — Spike de APIs y fuentes para obtener oportunidades laborales

**Estado:** ✅ Completado

**Qué se hizo:**
Se diseñó el schema de normalización de ofertas (`NormalizedJob`) para unificar respuestas de distintas fuentes, y se definió el contrato de fuentes de datos.

**Entregables:**

| Archivo | Descripción |
|---|---|
| [`docs/specs/job-sources-spec.md`](https://github.com/WalkerKenneth/JobSearcher/blob/main/docs/specs/job-sources-spec.md) | Schema `NormalizedJob`, campos requeridos/opcionales por fuente, recomendación MVP |
| [`fixtures/jobs/jsearch_raw_example.json`](https://github.com/WalkerKenneth/JobSearcher/blob/main/fixtures/jobs/jsearch_raw_example.json) | Respuesta raw de JSearch para tests de normalización |
| [`fixtures/jobs/serpapi_raw_example.json`](https://github.com/WalkerKenneth/JobSearcher/blob/main/fixtures/jobs/serpapi_raw_example.json) | Respuesta raw de SerpAPI para tests de normalización |

**Conclusiones y decisiones:**

- Se definió `NormalizedJob` como el **único contrato de datos** que el `ScoringEngine` puede consumir — nunca respuestas raw de APIs. Esto desacopla el pipeline de scoring de cualquier cambio en la API fuente.
- Los campos de salario (`salary_min`, `salary_max`, `salary_currency`) son `nullable` por diseño, dado que están ausentes en ~75% de las ofertas LATAM.
- Se definió el algoritmo de construcción de queries desde `StudentProfile`: `"{seniority} {rol_preferido} {tech_primaria}"` (e.g., `"junior Frontend Developer React"`).
- Se establecieron **restricciones de implementación no negociables:** cache obligatorio de 24h por query, prohibición de scraping directo (solo APIs contractuales), freshness máxima de 30 días (`date_posted: month`), y `NormalizedJob` como único contrato del scoring engine.
- **Trigger de migración a SerpAPI definido:** <5 resultados relevantes por perfil con JSearch, cohort >50 estudiantes, o expansión a más de 2 países LATAM simultáneamente.

---

## Subtarea 5 — Diseñar pipeline de ingesta, normalización y almacenamiento

**Estado:** ✅ Completado

**Qué se hizo:**
Se diseñó el schema de almacenamiento persistente (`StoredJob`), la lógica de deduplicación en 3 niveles y el contrato de la capa de base de datos.

**Entregables:**

| Archivo | Descripción |
|---|---|
| [`docs/specs/job-storage-spec.md`](https://github.com/WalkerKenneth/JobSearcher/blob/main/docs/specs/job-storage-spec.md) | Schema `StoredJob`, estrategia de dedup, modelo ER |
| [`fixtures/jobs/stored_job_frontend.json`](https://github.com/WalkerKenneth/JobSearcher/blob/main/fixtures/jobs/stored_job_frontend.json) | Fixture: oferta frontend normalizada y almacenada |
| [`fixtures/jobs/stored_job_backend.json`](https://github.com/WalkerKenneth/JobSearcher/blob/main/fixtures/jobs/stored_job_backend.json) | Fixture: oferta backend normalizada y almacenada |
| [`fixtures/jobs/stored_job_duplicate.json`](https://github.com/WalkerKenneth/JobSearcher/blob/main/fixtures/jobs/stored_job_duplicate.json) | Fixture: duplicado para tests de deduplicación |

**Conclusiones y decisiones:**

- La deduplicación se diseñó en **3 niveles en cascada** para cubrir duplicados exactos, cross-source y semánticos: (1) `apply_url` exacta, (2) `source + job_id`, (3) `dedup_key` (hash de título + empresa + ubicación normalizada). Si cualquier nivel hace match, la oferta no se inserta.
- Se eligió **SQLite** como base de datos para el MVP por portabilidad, sin servidor y compatibilidad directa con SQLAlchemy.
- El schema incluye un flag `is_active` para permitir expiración soft de ofertas sin borrado físico.

---

## Subtarea 6 — Implementar POC de ingesta de oportunidades laborales

**Estado:** ✅ Completado

**Qué se hizo:**
Se implementó el pipeline completo de ingesta: construcción de queries desde el perfil, fetch con retry, normalización JSearch/SerpAPI → `NormalizedJob`, y persistencia en SQLite con deduplicación en 3 niveles. **53 tests passing.**

**Entregables:**

| Archivo | Descripción |
|---|---|
| [`backend/ingest.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/ingest.py) | CLI: `python3 ingest.py <profile.json> [--dry-run] [--no-cache] [--profile-id <id>]` |
| [`backend/app/ingestion/query_builder.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/app/ingestion/query_builder.py) | Traduce `StudentProfile` a parámetros de JSearch/SerpAPI |
| [`backend/app/ingestion/fetcher.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/app/ingestion/fetcher.py) | HTTP client + retry (tenacity) + caché SQLite 24h |
| [`backend/app/ingestion/normalizer.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/app/ingestion/normalizer.py) | Raw JSearch/SerpAPI → `NormalizedJob`; genera `dedup_key` |
| [`backend/app/ingestion/repository.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/app/ingestion/repository.py) | Dedup 3 niveles + persistencia `StoredJob`; `load_active_jobs()` |
| [`backend/app/db/models.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/app/db/models.py) | SQLAlchemy models: `job_postings`, `raw_snapshots`, `query_cache` |
| [`backend/tests/test_ingestion.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/tests/test_ingestion.py) | Tests de integración del pipeline |
| [`backend/tests/test_normalizer.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/tests/test_normalizer.py) | Tests unitarios del normalizer |
| [`backend/tests/test_deduplication.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/tests/test_deduplication.py) | Tests de los 3 niveles de deduplicación |

**Conclusiones y decisiones:**

- El pipeline fue implementado y validado end-to-end con 53 tests passing.
- La CLI acepta el perfil como archivo JSON o como `--profile-id` desde DB, lo que preparó el terreno para la gestión de perfiles en base de datos (subtarea 8).
- El uso de `tenacity` para retry con backoff exponencial evita fallos por rate limit transitorios de JSearch sin inflar la complejidad del código.
- El caché SQLite de 24h por query hash permite que múltiples ejecuciones para el mismo perfil no consuman rate limit adicional.
- Requiere: `JSEARCH_API_KEY` en `backend/.env`.

---

## Subtarea 7 — Implementar scoring y curación de oportunidades

**Estado:** ✅ Completado

**Qué se hizo:**
Se implementó el motor de scoring en 2 fases: filtros duros (salario, modalidad, ubicación) y puntuación 0–100 con 7 componentes ponderados. **50 tests passing.**

**Componentes de score:**

| Componente | Puntos |
|---|---|
| Stack técnico | 35–40 pts |
| Seniority | 15–20 pts |
| Idioma | 15 pts |
| Sector | 15 pts |
| Tamaño de empresa | 10 pts |
| Título del rol | 5 pts |
| Ajuste salarial | penalización –10 |

**Entregables:**

| Archivo | Descripción |
|---|---|
| [`backend/app/schemas.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/app/schemas.py) | `StudentProfile` dataclass + nested schemas con `from_dict()` |
| [`backend/app/scoring/scorer.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/app/scoring/scorer.py) | `apply_hard_filters()`, `score_job()`, `rank_jobs()`; ajustes por `growth_priority` |
| [`backend/tests/test_scorer.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/tests/test_scorer.py) | 50 tests: filtros duros, componentes de score, penalizaciones, ranking |

**Conclusiones y decisiones:**

- Se implementaron las 3 funciones clave del motor: `apply_hard_filters()` (elimina por restricciones absolutas), `score_job()` (calcula compatibilidad 0–100) y `rank_jobs()` (ordena y filtra por score mínimo).
- Los ajustes de `growth_priority` fueron implementados: `learning` aumenta el peso de stack match en +5 pts y reduce seniority en –5; `salary` da +10 bonus si la oferta supera el salario máximo esperado; `stability` da +10 extra a empresas enterprise/mid-size; `impact` da +10 al sector si es ONG/govtech/social impact.
- `StudentProfile` se implementó como dataclass Python con método `from_dict()` en cada clase anidada, lo que permite carga directa desde JSON sin librerías externas.
- El scorer es **completamente determinístico y testeable** con unit tests normales — no involucra al LLM, siguiendo la regla de arquitectura de ADR-001.

---

## Subtarea 8 — Definir flujo de entrega y feedback para recomendaciones

**Estado:** ✅ Completado

**Qué se hizo:**
Se diseñó e implementó el flujo completo de entrega de recomendaciones (CLI + JSON) y el ciclo de feedback con máquina de estados de 5 estados. Los perfiles se gestionan completamente desde base de datos. **146 tests passing en total acumulado.**

**Máquina de estados de feedback:**

```
recommended → seen → applied (terminal)
           → discarded (terminal)
           → needs_coach → applied (coach puede mover)
```

**Entregables:**

| Archivo | Descripción |
|---|---|
| [`docs/specs/delivery-feedback-spec.md`](https://github.com/WalkerKenneth/JobSearcher/blob/main/docs/specs/delivery-feedback-spec.md) | Canal de entrega, schema `RecommendationPayload`, estados de feedback, criterios de aceptación |
| [`backend/app/delivery/payload.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/app/delivery/payload.py) | `RecommendationPayload`, `build_payload()`, `build_recommendations()` |
| [`backend/app/delivery/repository.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/app/delivery/repository.py) | `save_recommendations()`, `record_feedback()`, `get_recommendations()`, `get_feedback_events()` |
| [`backend/recommend.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/recommend.py) | CLI: carga perfil → jobs de DB → score → guarda → imprime tabla/JSON |
| [`backend/feedback.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/feedback.py) | CLI: `python feedback.py <rec_id> <status> [--note "..."]` |
| [`backend/app/profiles/repository.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/app/profiles/repository.py) | `upsert_profile`, `load_profile`, `list_profiles`, `delete_profile` |
| [`backend/profiles.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/profiles.py) | CLI: `import <file>`, `list`, `show <id>`, `delete <id>` |
| [`backend/tests/test_delivery.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/tests/test_delivery.py) | Tests del pipeline de entrega y feedback |
| [`backend/tests/test_profiles.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/tests/test_profiles.py) | 8 tests: insert, update, roundtrip, list, delete de perfiles |

**Conclusiones y decisiones:**

- **Canal MVP: CLI + JSON.** Se evaluaron 4 opciones (CLI, email, Slack/Discord, FastAPI REST) y se eligió CLI por ausencia de dependencias extra y velocidad de validación. La integración con FastAPI (subtarea 9) fue el paso natural siguiente, ya establecido en ADR-001.
- **Lógica de upsert con preservación de estado:** en re-ejecuciones del agente, el score y reasons/gaps se actualizan, pero el `status` de feedback se preserva si ya fue modificado por el usuario (≠ `recommended`). Esto evita perder el historial de decisiones del estudiante.
- **`feedback_events` es append-only:** cada cambio de estado genera un nuevo registro, permitiendo reconstruir el historial completo de decisiones por oportunidad.
- **Perfiles migrados a DB:** los perfiles pasaron de ser leídos solo desde archivos JSON a gestionarse completamente en la tabla `profiles`, con soporte de `upsert` (actualización sin duplicados), `load_profile`, `list_profiles` y `delete_profile`. Esto desacopló el agente del sistema de archivos.
- El `next_action` generado para el estudiante se determina automáticamente por umbral de score: ≥80 = "Aplicar de inmediato", ≥60 = "Aplicar con adaptaciones menores al CV", ≥40 = "Revisar gaps antes de aplicar", <40 = "Match bajo — fuera del rango recomendado".

---

## Subtarea 9 — FastAPI Backend + React Frontend (POC interfaz)

**Estado:** ✅ Completado

**Qué se hizo:**
Se implementó una API REST con FastAPI que expone los endpoints del pipeline (jobs, recomendaciones) y un frontend React/Vite para visualización de ofertas y recomendaciones.

**Entregables:**

| Archivo | Descripción |
|---|---|
| [`backend/api.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/api.py) | FastAPI app: endpoints para jobs y recomendaciones |
| [`backend/jobs.py`](https://github.com/WalkerKenneth/JobSearcher/blob/main/backend/jobs.py) | CLI: `list_all_jobs`, `load_job` queries |
| [`frontend/src/App.jsx`](https://github.com/WalkerKenneth/JobSearcher/blob/main/frontend/src/App.jsx) | App React: tabs de Jobs y Recomendaciones |
| [`frontend/src/JobsTab.jsx`](https://github.com/WalkerKenneth/JobSearcher/blob/main/frontend/src/JobsTab.jsx) | Vista de listado de ofertas |
| [`frontend/src/RecommendationsTab.jsx`](https://github.com/WalkerKenneth/JobSearcher/blob/main/frontend/src/RecommendationsTab.jsx) | Vista de recomendaciones rankeadas |
| [`frontend/src/api.js`](https://github.com/WalkerKenneth/JobSearcher/blob/main/frontend/src/api.js) | Cliente HTTP hacia la API FastAPI |

**Conclusiones y decisiones:**

- La implementación de FastAPI concreta la arquitectura definida en ADR-001: el backend expone los datos del pipeline via REST, el frontend consume esos endpoints sin lógica de negocio propia.
- El stack React/Vite fue elegido por velocidad de setup para el POC. El build de producción está incluido en `frontend/dist/`.
- Esta subtarea valida el camino completo de extremo a extremo: ingesta → scoring → recomendaciones → visualización en UI.

---

## Resumen ejecutivo

| # | Subtarea | Estado | Tests |
|---|---|---|---|
| 1 | Definir perfil del candidato y criterios de match | ✅ | — |
| 2 | Spike de soluciones para búsqueda de empleo | ✅ | — |
| 3 | Evaluar orquestación (OpenClaw vs Hermes) | ✅ | — |
| 4 | Spike de APIs y fuentes de oportunidades | ✅ | — |
| 5 | Diseñar pipeline de ingesta y almacenamiento | ✅ | — |
| 6 | Implementar POC de ingesta | ✅ | 53 |
| 7 | Implementar scoring y curación | ✅ | 50 |
| 8 | Flujo de entrega, feedback y gestión de perfiles | ✅ | 146 (acumulado) |
| 9 | FastAPI backend + React frontend | ✅ | — |

**Repositorio:** https://github.com/WalkerKenneth/JobSearcher
