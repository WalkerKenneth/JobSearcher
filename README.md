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

## Subtareas

| #   | Nombre                                                       | Estado        | Artefactos                                                                                                          |
| --- | ------------------------------------------------------------ | ------------- | ------------------------------------------------------------------------------------------------------------------- |
| 1   | Definir perfil del candidato y criterios de match            | ✅ Completada | [spec](docs/specs/student-profile-spec.md) · [rúbrica](docs/specs/match-rubric.md) · [fixtures](fixtures/profiles/) |
| 2   | Spike de soluciones existentes para búsqueda de empleo       | ✅ Completada | [spike](docs/spikes/job-search-tools-spike.md)                                                                      |
| 3   | Evaluar OpenClaw vs Hermes para orquestación del agente      | ✅ Completada | [ADR-001](docs/decisions/adr-001-orchestration.md) · [flujo mínimo](docs/spikes/orchestration-minimal-flow/)        |
| 4   | Spike de APIs y fuentes para obtener oportunidades laborales | ✅ Completada | [spec](docs/specs/job-sources-spec.md)                                                                              |
| 5   | Diseñar pipeline de ingesta, normalización y almacenamiento  | ✅ Completada | [spec](docs/specs/job-storage-spec.md) · [fixtures](fixtures/jobs/)                                                 |
| 6   | Implementar POC de ingesta de oportunidades laborales        | ✅ Completada | [backend/](backend/) — `ingest.py`, `JobFetcher`, `JobNormalizer`, `JobRepository`                                  |
| 7   | Implementar scoring y curación de oportunidades              | ✅ Completada | [scorer.py](backend/app/scoring/scorer.py) — filtros obligatorios + score 0–100                                     |
| 8   | Definir flujo de entrega y feedback para recomendaciones     | ✅ Completada | [delivery/](backend/app/delivery/) — `recommend.py`, `feedback.py`, 138 tests                                       |

---

## Estructura del Proyecto

```
JobSearcher/
├── backend/
│   ├── app/
│   │   ├── config.py                      # Variables de entorno (DATABASE_URL, JSEARCH_API_KEY)
│   │   ├── schemas.py                     # NormalizedJob, StudentProfile, dataclasses compartidas
│   │   ├── db/
│   │   │   ├── models.py                  # SQLAlchemy: job_postings, raw_snapshots, query_cache,
│   │   │   │                              #             recommendations, feedback_events
│   │   │   └── session.py                 # Engine SQLite + creación de tablas e índices
│   │   ├── ingestion/
│   │   │   ├── query_builder.py           # StudentProfile → parámetros de API JSearch
│   │   │   ├── fetcher.py                 # HTTP JSearch + caché 24h + retry exponencial
│   │   │   ├── normalizer.py              # Raw API → NormalizedJob + dedup_key SHA-256
│   │   │   └── repository.py             # Dedup 3 niveles + persistencia + load_active_jobs
│   │   ├── scoring/
│   │   │   └── scorer.py                  # Fase 1: hard filters  |  Fase 2: score 0–100
│   │   │                                  # Dimensiones: stack, seniority, idioma, sector,
│   │   │                                  #              empresa, título, salario
│   │   └── delivery/
│   │       ├── payload.py                 # RecommendationPayload + build_recommendations()
│   │       └── repository.py             # Upsert recomendaciones + record_feedback()
│   ├── tests/
│   │   ├── conftest.py                    # Fixtures compartidos: profile, jobs, DB en memoria
│   │   ├── test_normalizer.py             # Normalización de campos, URL, seniority, stack
│   │   ├── test_deduplication.py          # Dedup niveles 1/2/3 + idempotencia
│   │   ├── test_ingestion.py             # Pipeline completo con fixtures
│   │   ├── test_scorer.py                 # Hard filters + scoring por dimensión + rank_jobs
│   │   └── test_delivery.py               # build_payload, save_recommendations, record_feedback
│   ├── ingest.py                          # CLI: ingestar ofertas desde API
│   ├── recommend.py                       # CLI: generar recomendaciones para un perfil
│   ├── feedback.py                        # CLI: registrar feedback del estudiante
│   ├── requirements.txt
│   └── .env.example
├── docs/
│   ├── decisions/
│   │   └── adr-001-orchestration.md       # Decisión de capa de orquestación
│   ├── specs/
│   │   ├── student-profile-spec.md        # Contrato de datos del perfil
│   │   ├── match-rubric.md                # Rúbrica de compatibilidad
│   │   ├── job-sources-spec.md            # APIs de empleo: comparativa y NormalizedJob
│   │   ├── job-storage-spec.md            # Schema StoredJob, dedup y almacenamiento
│   │   └── delivery-feedback-spec.md      # Flujo de entrega y ciclo de feedback
│   └── spikes/
│       ├── job-search-tools-spike.md      # Evaluación de herramientas existentes
│       └── orchestration-minimal-flow/
│           └── minimal_flow.py            # Prueba del pipeline end-to-end
├── fixtures/
│   ├── profiles/
│   │   ├── junior_frontend.json           # Perfil de prueba: frontend
│   │   └── junior_fullstack.json          # Perfil de prueba: fullstack/backend
│   └── jobs/
│       ├── jsearch_raw_example.json       # Respuesta raw de JSearch
│       ├── serpapi_raw_example.json       # Respuesta raw de SerpAPI
│       ├── stored_job_frontend.json       # StoredJob: oferta frontend
│       ├── stored_job_backend.json        # StoredJob: oferta backend
│       └── stored_job_duplicate.json      # StoredJob: caso duplicado
└── README.md
```

---

## Cómo iniciar el proyecto

### Requisitos previos

- Python 3.11 o superior
- Una API key de [JSearch en RapidAPI](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) (plan gratuito disponible)

### 1. Clonar e instalar dependencias

```bash
git clone <repo-url>
cd JobSearcher/backend

# Crear entorno virtual (recomendado)
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` y agregar la API key:

```dotenv
JSEARCH_API_KEY=tu_api_key_aqui
DATABASE_URL=sqlite:///data/jobs.db   # valor por defecto, no requiere cambio
```

### 3. Ingestar ofertas laborales

El comando `ingest.py` consulta la API de JSearch usando el perfil del estudiante, normaliza las ofertas y las guarda en la base de datos local (`data/jobs.db`).

```bash
# Ingesta estándar con perfil de prueba
python3 ingest.py ../fixtures/profiles/junior_frontend.json

# Dry-run: muestra resultados sin escribir en BD
python3 ingest.py ../fixtures/profiles/junior_frontend.json --dry-run

# Forzar llamada a API ignorando caché de 24h
python3 ingest.py ../fixtures/profiles/junior_frontend.json --no-cache

# Usar perfil fullstack/backend
python3 ingest.py ../fixtures/profiles/junior_fullstack.json
```

### 4. Generar recomendaciones

`recommend.py` carga los jobs almacenados, aplica filtros obligatorios, calcula el score 0–100 para cada oferta y guarda las recomendaciones en la BD y en `data/recommendations_<profile_id>.json`.

```bash
# Recomendaciones en formato tabla (default)
python3 recommend.py ../fixtures/profiles/junior_frontend.json

# Limitar a top 5
python3 recommend.py ../fixtures/profiles/junior_frontend.json --top 5

# Salida en JSON
python3 recommend.py ../fixtures/profiles/junior_frontend.json --format json
```

**Ejemplo de salida:**

```
════════════════════════════════════════════════════════════
TOP 5 RECOMENDACIONES — Valentina Morales
════════════════════════════════════════════════════════════
#01  Frontend Developer
     Acme Corp  |  Remoto (Chile)
     Score: [████████████████░░░░]  82
     Acción: Aplicar de inmediato
     ✓ Stack: react, typescript (2/3); Seniority compatible
     ID: valentina_001_jsearch_abc123
```

### 5. Registrar feedback

```bash
# Marcar como aplicada
python3 feedback.py valentina_001_jsearch_abc123 applied

# Descartar con nota
python3 feedback.py valentina_001_jsearch_abc123 discarded --note "Sector gambling"

# Marcar como vista y ver historial
python3 feedback.py valentina_001_jsearch_abc123 seen --history

# Estados disponibles: recommended | seen | applied | discarded | needs_coach
```

### 6. Correr tests

```bash
# Todos los tests
python3 -m pytest tests/ -v

# Tests por módulo
python3 -m pytest tests/test_scorer.py -v
python3 -m pytest tests/test_delivery.py -v
python3 -m pytest tests/test_normalizer.py -v

# Con reporte de cobertura
python3 -m pytest tests/ --tb=short -q
```

---

## Flujo completo

```
fixtures/profiles/junior_frontend.json
        │
        ▼
   ingest.py  ──→  JSearch API  ──→  normalizar  ──→  data/jobs.db
        │
        ▼
 recommend.py  ──→  score 0–100  ──→  data/recommendations_*.json
                                             │
                                             ▼
                                       feedback.py  ──→  feedback_events en BD
```

---

## Contexto del Programa

**Lyfter** es un programa de aprendizaje que forma a estudiantes en desarrollo de software. Este agente es una herramienta interna para acelerar su inserción laboral al finalizar la formación.

Los datos del perfil se originan en el sistema **Ipsum** de Lyfter. Ver [student-profile-spec.md](docs/specs/student-profile-spec.md) para el mapeo completo de fuentes → campos del perfil.
