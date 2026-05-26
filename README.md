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

| #   | Nombre                                                       | Estado        | Artefactos                                                                                                           |
| --- | ------------------------------------------------------------ | ------------- | -------------------------------------------------------------------------------------------------------------------- |
| 1   | Definir perfil del candidato y criterios de match            | ✅ Completada | [spec](docs/specs/student-profile-spec.md) · [rúbrica](docs/specs/match-rubric.md) · [fixtures](fixtures/profiles/) |
| 2   | Spike de soluciones existentes para búsqueda de empleo       | ✅ Completada | [spike](docs/spikes/job-search-tools-spike.md)                                                                       |
| 3   | Evaluar OpenClaw vs Hermes para orquestación del agente      | ✅ Completada | [ADR-001](docs/decisions/adr-001-orchestration.md) · [flujo mínimo](docs/spikes/orchestration-minimal-flow/)         |
| 4   | Spike de APIs y fuentes para obtener oportunidades laborales | ✅ Completada | [spec](docs/specs/job-sources-spec.md)                                                                               |
| 5   | Diseñar pipeline de ingesta, normalización y almacenamiento  | ✅ Completada | [spec](docs/specs/job-storage-spec.md) · [fixtures](fixtures/jobs/)                                                  |
| 6   | Implementar POC de ingesta de oportunidades laborales        | ✅ Completada | [backend/](backend/) — `ingest.py`, `JobFetcher`, `JobNormalizer`, `JobRepository`, 53 tests                         |
| 7   | Implementar scoring y curación de oportunidades              | ⬜ Pendiente  | —                                                                                                                    |
| 8   | Definir flujo de entrega y feedback para recomendaciones     | ⬜ Pendiente  | —                                                                                                                    |

---

## Estructura del Proyecto

```
JobSearcher/
├── backend/                               # ← Subtarea 6: POC de ingesta
│   ├── app/
│   │   ├── config.py                      # Variables de entorno
│   │   ├── schemas.py                     # NormalizedJob dataclass
│   │   ├── db/
│   │   │   ├── models.py                  # SQLAlchemy: job_postings, raw_snapshots, query_cache
│   │   │   └── session.py                 # Engine SQLite + índices
│   │   └── ingestion/
│   │       ├── query_builder.py           # StudentProfile → parámetros de API
│   │       ├── fetcher.py                 # HTTP JSearch + caché 24h + retry
│   │       ├── normalizer.py              # Raw API → NormalizedJob + dedup_key
│   │       └── repository.py             # Dedup 3 niveles + persistencia
│   ├── tests/
│   │   ├── test_normalizer.py             # 28 tests: normalización, URL, seniority, stack
│   │   ├── test_deduplication.py          # 15 tests: niveles 1/2/3 + idempotencia
│   │   └── test_ingestion.py             # 10 tests: pipeline completo con fixtures
│   ├── ingest.py                          # CLI: python ingest.py <profile.json>
│   ├── requirements.txt
│   └── .env.example
├── docs/
│   ├── decisions/
│   │   └── adr-001-orchestration.md       # Decisión de capa de orquestación
│   ├── specs/
│   │   ├── student-profile-spec.md        # Contrato de datos del perfil
│   │   ├── match-rubric.md                # Rúbrica de compatibilidad
│   │   ├── job-sources-spec.md            # APIs de empleo: comparativa y NormalizedJob
│   │   └── job-storage-spec.md            # Schema StoredJob, dedup y almacenamiento
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

### Uso del comando de ingesta (subtarea 6)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # Agregar JSEARCH_API_KEY

# Ingesta con perfil de prueba
python3 ingest.py ../fixtures/profiles/junior_frontend.json

# Dry-run (sin escribir en BD)
python3 ingest.py ../fixtures/profiles/junior_frontend.json --dry-run

# Forzar llamada a API (ignorar caché 24h)
python3 ingest.py ../fixtures/profiles/junior_frontend.json --no-cache

# Correr tests
python3 -m pytest tests/ -v
```

---

## Contexto del Programa

**Lyfter** es un programa de aprendizaje que forma a estudiantes en desarrollo de software. Este agente es una herramienta interna para acelerar su inserción laboral al finalizar la formación.

Los datos del perfil se originan en el sistema **Ipsum** de Lyfter. Ver [student-profile-spec.md](docs/specs/student-profile-spec.md) para el mapeo completo de fuentes → campos del perfil.
