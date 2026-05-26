# Spec: Flujo de Entrega y Feedback de Recomendaciones (Subtarea 8)

## Contexto

El motor de scoring (subtarea 7) produce una lista rankeada de `JobMatch` por perfil. Esta
spec define cómo esos matches se convierten en recomendaciones accionables que el
estudiante o coach puede consumir, y cómo se captura su feedback para cerrar el loop.

---

## 1. Canal de entrega (MVP)

**Decisión: CLI + JSON file.**

| Opción | Pros | Cons |
|--------|------|------|
| CLI (stdout + JSON) | Sin dependencias extra, inmediato | No hay UI |
| Email | Familiar para coaches | SMTP setup, HTML template |
| Slack/Discord | Notificaciones push | OAuth, webhook config |
| FastAPI REST | Ruta natural hacia frontend | Requiere frontend activo |

Para el MVP el canal es la terminal: `recommend.py` imprime la lista y escribe un JSON
en `data/recommendations_{profile_id}.json`. La integración con FastAPI es el siguiente
paso natural (ADR-001 ya lo establece como arquitectura objetivo).

El feedback se registra vía CLI: `feedback.py <rec_id> <status>`.

---

## 2. Formato del payload de recomendación

```
RecommendationPayload
├── rec_id          str              # "{profile_id}_{job_id}"
├── profile_id      str              # ID del estudiante
├── generated_at    str (ISO-8601)   # timestamp de generación
├── job_id          str              # FK → job_postings.job_id
├── title           str              # título del puesto
├── company         str              # nombre de la empresa
├── apply_url       str              # link de aplicación
├── modality        list[str]        # ["remote", "hybrid", "on-site"]
├── location        str              # "Remoto (San José, Costa Rica)"
├── match_score     int              # 0–100
├── match_reasons   list[str]        # por qué es un buen match
├── gaps            list[str]        # qué falta o penaliza
├── next_action     str              # texto accionable
└── status          str              # ver sección 3
```

### Umbrales de `next_action`

| Score | Texto |
|-------|-------|
| ≥ 80  | "Aplicar de inmediato" |
| ≥ 60  | "Aplicar con adaptaciones menores al CV" |
| ≥ 40  | "Revisar gaps antes de aplicar" |
| < 40  | "Match bajo — fuera del rango recomendado" |

---

## 3. Estados de feedback

```
recommended ──→ seen ──→ applied
     │                    └──→ (terminal)
     └──→ discarded (terminal)
     └──→ needs_coach
              └──→ applied (coach puede mover)
```

| Estado | Descripción |
|--------|-------------|
| `recommended` | Generado por el sistema, aún no revisado |
| `seen` | El estudiante lo vio pero no tomó acción |
| `discarded` | Descartado explícitamente (no aplica) |
| `applied` | El estudiante aplicó |
| `needs_coach` | Requiere revisión o ayuda del coach |

---

## 4. Persistencia

### Tabla: `recommendations`

```sql
rec_id           TEXT PRIMARY KEY    -- "{profile_id}_{job_id}"
profile_id       TEXT NOT NULL
job_id           TEXT NOT NULL FK→job_postings
generated_at     TEXT NOT NULL       -- ISO-8601
match_score      INTEGER NOT NULL
match_reasons    TEXT NOT NULL       -- JSON array
gaps             TEXT NOT NULL       -- JSON array
next_action      TEXT NOT NULL
status           TEXT NOT NULL DEFAULT 'recommended'
status_updated_at TEXT NOT NULL
```

**Lógica de upsert:** en re-ejecuciones, se actualiza score/reasons/gaps pero se
preserva el status si ya fue modificado por el usuario (≠ 'recommended').

### Tabla: `feedback_events`

```sql
id           INTEGER PRIMARY KEY AUTOINCREMENT
rec_id       TEXT NOT NULL FK→recommendations
status       TEXT NOT NULL        -- estado al que se transicionó
note         TEXT NOT NULL DEFAULT ''
recorded_at  TEXT NOT NULL        -- ISO-8601
```

Append-only. Permite reconstruir el historial de decisiones por oportunidad.

---

## 5. CLI

### `recommend.py`

```
python recommend.py fixtures/profiles/junior_frontend.json [--top 10] [--format table|json]
```

Flujo:
1. Carga `StudentProfile` del JSON.
2. Lee jobs activos del DB (`job_postings WHERE is_active=1`).
3. Aplica `rank_jobs(jobs, profile)`.
4. Construye top-N `RecommendationPayload` (solo las que pasan hard filters).
5. Persiste en `recommendations` (upsert).
6. Imprime en tabla o JSON; escribe `data/recommendations_{profile_id}.json`.

### `feedback.py`

```
python feedback.py <rec_id> <status> [--note "Texto opcional"]
```

Flujo:
1. Valida que `rec_id` existe en DB.
2. Actualiza `recommendations.status` + `status_updated_at`.
3. Inserta fila en `feedback_events`.
4. Confirma en stdout.

---

## 6. Criterios de aceptación (spec-driven)

| # | Dado | Cuando | Entonces |
|---|------|--------|----------|
| 1 | Un ranking de jobs pasados por hard filters | Se llama `build_recommendations()` | Retorna lista de `RecommendationPayload` con todos los campos correctos |
| 2 | Una recomendación sin feedback previo | Se llama `save_recommendations()` | Se inserta con status='recommended' |
| 3 | Una recomendación ya en status='applied' | Se re-ejecuta `save_recommendations()` | El status se preserva (no se regresa a 'recommended') |
| 4 | Un `rec_id` válido | Se llama `record_feedback('applied')` | El status se actualiza y se inserta un `FeedbackEvent` |
| 5 | Un `rec_id` inexistente | Se llama `record_feedback()` | Retorna `False` sin lanzar excepción |
| 6 | Un perfil con jobs en DB | Se ejecuta `recommend.py` | Se imprime la tabla y se escribe el JSON |
