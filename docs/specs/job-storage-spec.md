# Spec: Almacenamiento y Normalización de Ofertas (`StoredJob`)

**Versión:** 1.1  
**Fecha:** 2026-05-26  
**Autor:** Equipo Lyfter  
**Estado:** Aprobado  
**Subtarea:** 5 — Almacenamiento y normalización de oportunidades  
**Dependencias:** [student-profile-spec.md](student-profile-spec.md) · [job-sources-spec.md](job-sources-spec.md) · [ADR-001](../decisions/adr-001-orchestration.md)

---

## 1. Objetivo

Definir cómo se almacenan, normalizan y deduplicar las ofertas de empleo capturadas por el `JobFetcher`. Cada oferta debe poder auditarse (raw response preservado), compararse con otras fuentes (schema unificado), y actualizarse en fetches posteriores sin crear duplicados.

---

## 2. Esquema de Datos: `StoredJob`

`StoredJob` extiende el contrato `NormalizedJob` definido en [job-sources-spec.md](job-sources-spec.md) con campos de trazabilidad y deduplicación.

```typescript
interface StoredJob {
  // ── Identificación ────────────────────────────────────────────────
  job_id: string;             // ID único: usa el ID nativo de la fuente si existe,
                              // o SHA-256(source + company + title + country)[:12]
  source: "jsearch" | "serpapi";
  dedup_key: string;          // SHA-256(normalize(company) + "|" + normalize(title) + "|" + country)[:16]
  canonical_id: string | null;// null si este ES el registro canónico; si es duplicado,
                              // apunta al job_id del canónico
  duplicate_ids: string[];    // job_ids de registros que son duplicados de este (si es canónico)

  // ── Trazabilidad de captura ───────────────────────────────────────
  first_seen: string;         // ISO 8601 — primer fetch que encontró esta oferta
  last_seen: string;          // ISO 8601 — fetch más reciente que la encontró
  fetched_at: string;         // ISO 8601 — cuándo se ejecutó el fetch actual
  fetch_count: number;        // cuántas veces ha aparecido en fetches acumulados
  status: "active" | "stale" | "expired";
  is_active: boolean;         // false cuando status = "expired"

  // ── Datos básicos ─────────────────────────────────────────────────
  job_title: string;
  company_name: string;
  location_city: string | null;
  location_country: string;   // ISO nombre largo ("Costa Rica") o código ISO 3166-1 ("CR")
  is_remote: boolean;
  modality: ("remote" | "hybrid" | "on-site")[];

  // ── Compensación (nullable — ausente en ~75% de ofertas LATAM) ────
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;   // ISO 4217 ("CRC", "USD", "MXN")
  salary_period: "monthly" | "annual" | null;

  // ── Contenido ─────────────────────────────────────────────────────
  description_raw: string;          // Texto completo de la descripción
  qualifications_raw: string[];     // job_highlights.Qualifications (SerpAPI) o [] (JSearch)
  posted_at: string | null;         // ISO 8601 — fecha de publicación original

  // ── Señales inferidas (por LLM ExtractJobSignals) ─────────────────
  stack_keywords: string[];         // Tecnologías detectadas en description_raw
  seniority_signal: "junior" | "mid" | "senior" | "unknown";

  // ── Acción ────────────────────────────────────────────────────────
  apply_url: string;

  // ── Auditoría ─────────────────────────────────────────────────────
  raw_response: object;             // Respuesta original completa de la API (sin modificar)
}
```

### 2.1 Diferencias respecto a `NormalizedJob`

| Campo nuevo | Tipo | Propósito |
|-------------|------|-----------|
| `dedup_key` | string | Fingerprint para detectar duplicados cross-source |
| `canonical_id` | string \| null | Enlace al registro canónico si es duplicado |
| `duplicate_ids` | string[] | Registro inverso de duplicados en el canónico |
| `first_seen` | string | Auditoría de cuándo se detectó la oferta por primera vez |
| `last_seen` | string | Base para reglas de freshness |
| `fetch_count` | number | Indica qué tan consistente es la oferta (>1 = se ve repetidamente) |
| `status` | enum | Estado de frescura calculado desde `last_seen` |
| `is_active` | boolean | Flag rápido para filtrar expiradas sin calcular fechas |

---

## 3. Almacenamiento Inicial

### 3.1 Decisión: SQLite (MVP)

**Por qué SQLite:**
- Cero infraestructura adicional — un archivo `.db` en el mismo servidor FastAPI
- Suficiente para el volumen del MVP: 30 estudiantes × ~150 jobs/semana = ~4,500 registros totales
- Misma interfaz que PostgreSQL vía SQLAlchemy → migración es cambiar el `DATABASE_URL`, no reescribir código
- Permite auditoría directa (`sqlite3 jobs.db`) sin herramientas adicionales

**Cuándo migrar a PostgreSQL:**
- Cohort supera 100 estudiantes activos concurrentes
- Tamaño del archivo `.db` supera 500 MB
- Se necesitan búsquedas full-text en `description_raw` con ranking (PostgreSQL `tsvector`)

### 3.2 Tablas

#### Tabla `profiles`

Almacena los perfiles de estudiantes. Las estructuras anidadas (`stack`, `location`, etc.) se serializan como JSON text para mantener consistencia con el resto del esquema SQLite.

```sql
CREATE TABLE IF NOT EXISTS profiles (
    profile_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    cohort          TEXT NOT NULL DEFAULT '',
    seniority       TEXT NOT NULL CHECK(seniority IN ('junior', 'mid')),
    modality        TEXT NOT NULL DEFAULT '[]',        -- JSON array

    stack           TEXT NOT NULL DEFAULT '{}',        -- JSON: {primary, secondary, tools}
    location        TEXT NOT NULL DEFAULT '{}',        -- JSON: {city, country, timezone}
    languages       TEXT NOT NULL DEFAULT '[]',        -- JSON: [{language, level}]
    availability    TEXT NOT NULL DEFAULT '{}',        -- JSON: {start_date, hours_per_week, type}
    expected_salary TEXT NOT NULL DEFAULT '{}',        -- JSON: {min, max, currency, period}
    restrictions    TEXT NOT NULL DEFAULT '{}',        -- JSON: hard filters del estudiante
    preferences     TEXT NOT NULL DEFAULT '{}',        -- JSON: nice-to-have del estudiante

    created_at      TEXT NOT NULL,                     -- ISO 8601
    updated_at      TEXT NOT NULL                      -- ISO 8601 — se actualiza en cada upsert
);
```

Ver [student-profile-spec.md](student-profile-spec.md) para el esquema completo de campos y la API del repository.

#### Tabla `job_postings`

Almacena el registro normalizado + metadata de storage. Un registro por `job_id` canónico.

```sql
CREATE TABLE IF NOT EXISTS job_postings (
    job_id              TEXT PRIMARY KEY,
    source              TEXT NOT NULL CHECK(source IN ('jsearch', 'serpapi')),
    dedup_key           TEXT NOT NULL,
    canonical_id        TEXT REFERENCES job_postings(job_id),
    duplicate_ids       TEXT DEFAULT '[]',       -- JSON array serializado

    first_seen          TEXT NOT NULL,           -- ISO 8601
    last_seen           TEXT NOT NULL,           -- ISO 8601
    fetched_at          TEXT NOT NULL,           -- ISO 8601
    fetch_count         INTEGER NOT NULL DEFAULT 1,
    status              TEXT NOT NULL DEFAULT 'active'
                            CHECK(status IN ('active', 'stale', 'expired')),
    is_active           INTEGER NOT NULL DEFAULT 1,  -- 0 = false, 1 = true

    job_title           TEXT NOT NULL,
    company_name        TEXT NOT NULL,
    location_city       TEXT,
    location_country    TEXT NOT NULL,
    is_remote           INTEGER NOT NULL,             -- 0/1
    modality            TEXT NOT NULL DEFAULT '[]',   -- JSON array serializado
    apply_url           TEXT NOT NULL,

    salary_min          REAL,
    salary_max          REAL,
    salary_currency     TEXT,
    salary_period       TEXT CHECK(salary_period IN ('monthly', 'annual')),

    posted_at           TEXT,
    description_raw     TEXT NOT NULL,
    qualifications_raw  TEXT NOT NULL DEFAULT '[]',  -- JSON array serializado
    stack_keywords      TEXT NOT NULL DEFAULT '[]',  -- JSON array serializado
    seniority_signal    TEXT NOT NULL DEFAULT 'unknown'
                            CHECK(seniority_signal IN ('junior', 'mid', 'senior', 'unknown'))
);

-- Índices para deduplicación y búsqueda
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_dedup_key   ON job_postings(dedup_key) WHERE canonical_id IS NULL;
CREATE INDEX        IF NOT EXISTS idx_job_apply_url   ON job_postings(apply_url);
CREATE INDEX        IF NOT EXISTS idx_job_last_seen   ON job_postings(last_seen);
CREATE INDEX        IF NOT EXISTS idx_job_status      ON job_postings(status);
CREATE INDEX        IF NOT EXISTS idx_job_source      ON job_postings(source);
```

#### Tabla `raw_snapshots`

Preserva la respuesta cruda de cada fetch. Desacoplada de `job_postings` para que el raw no contamine el schema normalizado.

```sql
CREATE TABLE IF NOT EXISTS raw_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL REFERENCES job_postings(job_id),
    source      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,           -- ISO 8601
    raw_response TEXT NOT NULL           -- JSON serializado
);

CREATE INDEX IF NOT EXISTS idx_snapshot_job_id    ON raw_snapshots(job_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_fetched   ON raw_snapshots(fetched_at);
```

### 3.3 Variable de Entorno

```bash
DATABASE_URL=sqlite:///./data/jobs.db   # MVP
# DATABASE_URL=postgresql://user:pass@host/jobs  # Producción
```

---

## 4. Estrategia de Deduplicación

La deduplicación ocurre en el `JobNormalizer` **antes** de escribir en la base de datos. Tres niveles en orden de prioridad:

### Nivel 1 — Match exacto por `apply_url` (más confiable)

```python
def normalize_url(url: str) -> str:
    """Elimina parámetros de tracking (utm_*, ref=, etc.) y trailing slash."""
    parsed = urlparse(url)
    clean_params = {k: v for k, v in parse_qs(parsed.query).items()
                    if not k.startswith("utm_") and k not in ("ref", "source", "campaign")}
    return urlunparse(parsed._replace(query=urlencode(clean_params, doseq=True))).rstrip("/")
```

Si `normalize_url(new_job.apply_url)` ya existe en `job_postings.apply_url`:
→ No insertar. Actualizar `last_seen`, `fetch_count` y el snapshot raw.

### Nivel 2 — Match por `source + job_id` nativo

Si `source` y `job_id` ya existen en `job_postings`:
→ Mismo job, fetch posterior. Actualizar `last_seen`, `fetch_count`, snapshot.

### Nivel 3 — Deduplicación fuzzy cross-source por `dedup_key`

```python
import hashlib
import re

def build_dedup_key(company: str, title: str, country: str) -> str:
    """
    Genera un fingerprint normalizado para detectar el mismo job
    publicado en JSearch y SerpAPI simultáneamente.
    """
    def normalize(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"[^\w\s]", "", s)       # quitar puntuación
        s = re.sub(r"\s+", " ", s)           # colapsar espacios
        # Quitar sufijos genéricos de empresas
        for suffix in [" s.a.", " s.a.s.", " inc", " llc", " corp", " ltd", " s.r.l."]:
            s = s.replace(suffix, "")
        return s.strip()

    key = normalize(company) + "|" + normalize(title) + "|" + normalize(country)
    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

Si `dedup_key` ya existe en un registro con `canonical_id IS NULL` (es decir, en un registro canónico):
→ El nuevo registro es duplicado. Asignar `canonical_id` al existente.
→ Actualizar `duplicate_ids` del canónico con el nuevo `job_id`.
→ Conservar el registro con más campos no-null como canónico.

### 4.1 Selección del Registro Canónico

Cuando dos registros son deduplicados, el canónico es el que tiene mayor `completeness_score`:

```python
def completeness_score(job: StoredJob) -> int:
    score = 0
    if job.salary_min is not None:   score += 3
    if job.salary_max is not None:   score += 3
    if job.qualifications_raw:       score += 2
    if job.location_city is not None: score += 1
    if job.stack_keywords:           score += 1
    return score
```

El registro con mayor score se convierte en canónico (`canonical_id = null`). El otro recibe su `job_id` como `canonical_id`.

### 4.2 Flujo Completo de Deduplicación

```
nuevo_job (NormalizedJob)
    │
    ├─▶ [Nivel 1] ¿apply_url normalizada existe? ──── SÍ ──▶ UPDATE last_seen + fetch_count
    │                                                          INSERT raw_snapshot
    │                                                          STOP
    │   NO
    ├─▶ [Nivel 2] ¿source + job_id existe? ─────────── SÍ ──▶ (igual que Nivel 1)
    │
    │   NO
    ├─▶ [Nivel 3] ¿dedup_key existe? ───────────────── SÍ ──▶ Comparar completeness_score
    │                                                          Asignar canónico/duplicado
    │                                                          INSERT job_posting (con canonical_id)
    │                                                          UPDATE duplicate_ids del canónico
    │                                                          INSERT raw_snapshot
    │                                                          STOP
    │   NO
    └─▶ INSERT nuevo job_posting (canónico, canonical_id = null)
        INSERT raw_snapshot
```

---

## 5. Reglas de Freshness

El campo `status` se recalcula en cada fetch basado en `last_seen`:

```python
from datetime import datetime, timezone, timedelta

def compute_status(last_seen: str) -> tuple[str, bool]:
    """Retorna (status, is_active)."""
    delta = datetime.now(timezone.utc) - datetime.fromisoformat(last_seen)
    if delta <= timedelta(days=7):
        return "active", True
    elif delta <= timedelta(days=30):
        return "stale", True
    else:
        return "expired", False
```

| Estado | Condición | `is_active` | Comportamiento del agente |
|--------|-----------|-------------|--------------------------|
| `active` | `last_seen` ≤ 7 días | `true` | Se incluye en resultados de búsqueda |
| `stale` | 7 < `last_seen` ≤ 30 días | `true` | Se incluye pero con advertencia "oferta puede no estar vigente" |
| `expired` | `last_seen` > 30 días | `false` | Excluido del ranking; conservado en DB para auditoría |

**Frecuencia de actualización de `status`:**
- Se recalcula en cada fetch que incluye la query donde apareció el job.
- Un job `expired` puede volver a `active` si reaparece en un fetch posterior (la empresa puede haber republicado).

**Límite de freshness en la fuente:**
Ambas fuentes usan `date_posted: "month"` — ninguna oferta de más de 30 días entra al sistema. Por lo tanto, cualquier job con `first_seen` > 30 días y `last_seen` > 7 días ya pasó por el ciclo completo y puede marcarse `expired` con seguridad.

---

## 6. Ejemplos de Registros Normalizados

Ver fixtures en `fixtures/jobs/`:

| Archivo | Descripción |
|---------|-------------|
| [`jsearch_raw_example.json`](../../fixtures/jobs/jsearch_raw_example.json) | Respuesta cruda de JSearch para Valentina Torres |
| [`serpapi_raw_example.json`](../../fixtures/jobs/serpapi_raw_example.json) | Respuesta cruda de SerpAPI para Andrés Mejía |
| [`stored_job_frontend.json`](../../fixtures/jobs/stored_job_frontend.json) | `StoredJob` canónico — oferta frontend via JSearch |
| [`stored_job_backend.json`](../../fixtures/jobs/stored_job_backend.json) | `StoredJob` canónico — oferta backend via SerpAPI |
| [`stored_job_duplicate.json`](../../fixtures/jobs/stored_job_duplicate.json) | `StoredJob` duplicado cross-source (mismo job en JSearch y SerpAPI) |

---

## 7. Reglas de Validación al Ingresar un Job

Un `NormalizedJob` proveniente del `JobFetcher` debe pasar estas validaciones antes de almacenarse:

| Campo | Regla |
|-------|-------|
| `job_id` | No vacío; si fuente es `serpapi` y no tiene ID nativo, generar SHA-256 |
| `apply_url` | URL válida (comienza con `https://`); rechazar si malformada |
| `job_title` | No vacío |
| `company_name` | No vacío |
| `location_country` | No vacío |
| `description_raw` | Mínimo 50 caracteres; rechazar si es placeholder o error HTML |
| `posted_at` | Si presente, debe ser parseable a `datetime`; rechazar fechas futuras |
| `fetched_at` | Auto-asignado por el sistema al momento del fetch (no viene de la API) |

---

## 8. Estado de Implementación

| Item | Estado |
|------|--------|
| `JobRepository` — `upsert`, dedup 3 niveles, `load_active_jobs` | ✅ Implementado |
| `build_dedup_key` integrado en `JobNormalizer` | ✅ Implementado |
| `profiles` table + `ProfileRepository` | ✅ Implementado |
| `profiles.py` CLI (import, list, show, delete) | ✅ Implementado |
| `ingest.py` y `recommend.py` con `--profile-id` | ✅ Implementado |

## 9. Próximos Pasos

1. Implementar `update_freshness_status` como tarea periódica (cron diario) sobre todos los jobs `active` y `stale`.
2. Agregar migración inicial con `alembic` para tener `upgrade/downgrade` auditables.
3. Conectar `raw_snapshots` al pipeline de auditoría para permitir re-procesamiento de señales LLM sin re-fetching.
