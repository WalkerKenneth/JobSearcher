# Spec: Fuentes de Datos de Empleo

**Versión:** 1.0  
**Fecha:** 2026-05-25  
**Autor:** Equipo Lyfter  
**Estado:** Aprobado  
**Subtarea:** 4 — Motor de búsqueda de fuentes de empleo  

---

## 1. Objetivo

Definir qué fuentes de datos de empleo usará el agente JobSearcher, bajo qué condiciones y con qué contrato de datos. Esta spec es el input para el `JobFetcher` y el `JobNormalizer`.

**Perfil objetivo de búsqueda:**

- Estudiantes junior de Lyfter en Costa Rica (expansión futura: MX, CO, AR)
- Roles: frontend, backend, fullstack junior
- Modalidad: remoto e híbrido preferente
- Stack típico: JavaScript, React, Node.js

---

## 2. Tabla Comparativa de Fuentes

| Fuente | Método de acceso | Campos disponibles | Costo | Límite de uso | Riesgos |
|--------|-----------------|-------------------|-------|--------------|---------|
| **JSearch** (OpenWeb Ninja / RapidAPI) | REST API — GET con `query`, `location`, `num_pages` | título, empresa, ciudad, país, `is_remote`, descripción (texto libre), link de aplicación, salario (cuando existe) | Free: $0/mes · Pro: $25/mes · Ultra: $75/mes | Free: 200 req/mes · Pro: 10,000 req + $0.003 extra · Rate: 5 req/seg | Salario ausente en ~80% de ofertas CR; seniority y stack no estructurados — requieren NLP |
| **SerpAPI — Google Jobs** | REST API — GET con `engine=google_jobs`, `q`, `location`, `gl`, `hl` | título, empresa, ubicación, descripción, `job_highlights.Qualifications` (semiestructurado), `detected_extensions` (salario, modalidad, fecha), links | Free: $0/mes · Starter: $25/mes · Developer: $75/mes | Free: 100 búsquedas/mes · Starter: 1,000/mes · Developer: 5,000/mes · Créditos no rollean | Menor número de búsquedas free; créditos se pierden si no se usan en el mes |
| **Adzuna API** | REST API — GET oficial con `app_id`, `app_key`, `what`, `where` | título, empresa, descripción, categoría por sector, salario estimado, ubicación | Free: trial 14 días · Comercial: precio a consultar | ~250 req/mes en trial | Costa Rica no es país soportado — resultados nulos o incorrectos para el target |
| **JobSpy** (open source) | Librería Python — `scrape_jobs()` | DataFrame: título, empresa, ubicación, tipo de empleo, fecha, salario, descripción, URL | Gratis (solo infraestructura y proxies: ~$50-100/mes) | Sin límite técnico, pero rate-limited por LinkedIn (~10 páginas/IP) | Viola ToS de LinkedIn, Indeed y Glassdoor — **riesgo legal activo**, no apto para producción |
| **Apify — LinkedIn Jobs Scraper** | REST API para disparar actors + webhooks para resultados | JSON: título, empresa, ubicación, descripción, fecha, modalidad, link | $5/mes plataforma + $4.99-$29.99/mes por actor | Según plan del actor contratado | Dependencia de actor de tercero en marketplace — puede romperse o desaparecer; LinkedIn puede revocar acceso |

**Tabla de cobertura LATAM por fuente:**

| Fuente | Costa Rica | México | Colombia | Argentina |
|--------|-----------|--------|----------|-----------|
| JSearch | ✅ Alta | ✅ Alta | ✅ Alta | ✅ Alta |
| SerpAPI | ✅ Excelente | ✅ Excelente | ✅ Excelente | ✅ Excelente |
| Adzuna | ❌ No soportado | ✅ Sí | ❌ No soportado | ❌ No soportado |
| JobSpy | ⚠️ Limitada | ⚠️ Limitada | ⚠️ Limitada | ⚠️ Limitada |
| Apify | ⚠️ Moderada | ⚠️ Moderada | ⚠️ Moderada | ⚠️ Moderada |

---

## 3. Fuentes Seleccionadas para el POC

### 3.1 Fuente POC-1: JSearch API (free tier)

**Por qué:**
- Cero costo para validar hipótesis de cobertura
- Agrega Google for Jobs, que indexa Computrabajo CR, LinkedIn CR e Indeed CR
- Setup mínimo: un endpoint REST, sin tarjeta de crédito
- Upgrade path directo a Pro ($25/mes) cuando el cohort crezca

**Endpoint base:**
```
GET https://jsearch.p.rapidapi.com/search
```

**Headers requeridos:**
```
X-RapidAPI-Key: {JSEARCH_API_KEY}
X-RapidAPI-Host: jsearch.p.rapidapi.com
```

**Parámetros de query:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `query` | string | Término de búsqueda construido desde el perfil |
| `location` | string | País o ciudad de búsqueda |
| `remote_jobs_only` | boolean | `true` solo si `profile.restrictions.excluded_modalities` incluye `on-site` e `hybrid` |
| `date_posted` | string | `"month"` — frescura máxima 30 días |
| `num_pages` | int | 1-3 según presupuesto de rate limit |

---

### 3.2 Fuente POC-2: SerpAPI — Google Jobs (free tier)

**Por qué:**
- El campo `job_highlights.Qualifications` facilita extracción de stack sin NLP pesado
- Soporte nativo de idioma (`hl=es`) y país (`gl=cr`) — mejor targeting LATAM
- Estructura de respuesta más rica que JSearch para datos de seniority y beneficios
- Permite comparar calidad de datos vs. JSearch antes de decidir fuente MVP

**Endpoint base:**
```
GET https://serpapi.com/search
```

**Parámetros de query:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `engine` | string | Siempre `"google_jobs"` |
| `q` | string | Término de búsqueda construido desde el perfil |
| `location` | string | País o ciudad de búsqueda |
| `gl` | string | Código de país ISO 3166-1 alpha-2 (`"cr"`, `"mx"`, `"co"`) |
| `hl` | string | Idioma de resultados (`"es"` para español) |
| `chips` | string | `"date_posted:month"` — frescura máxima 30 días |
| `api_key` | string | Clave de SerpAPI |

---

## 4. Schema: NormalizedJob

Contrato de datos que **ambas fuentes deben producir** después de pasar por el `JobNormalizer`. Los campos marcados como `nullable` pueden ser `null` cuando la fuente no los provee.

```typescript
interface NormalizedJob {
  // Identificación y trazabilidad
  job_id: string;               // ID único de la oferta (generado si la fuente no lo provee)
  source: "jsearch" | "serpapi"; // Fuente de origen
  fetched_at: string;           // ISO 8601 — cuándo se consultó

  // Datos básicos
  job_title: string;
  company_name: string;
  location_city: string | null;
  location_country: string;
  is_remote: boolean;
  modality: ("remote" | "hybrid" | "on-site")[];  // inferido de is_remote + descripción

  // Datos de compensación (nullable — ausente en ~75% de ofertas LATAM)
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;   // ISO 4217 ("CRC", "USD", "MXN")
  salary_period: "monthly" | "annual" | null;

  // Datos de match
  description_raw: string;          // Texto completo de la descripción
  qualifications_raw: string[];     // job_highlights.Qualifications (SerpAPI) o [] (JSearch)
  posted_at: string | null;         // ISO 8601 o string relativo ("hace 2 días")

  // Acción
  apply_url: string;

  // Señales inferidas por NLP (opcional en fetch, requerido antes de scoring)
  stack_keywords: string[];         // Tecnologías detectadas en description_raw
  seniority_signal: "junior" | "mid" | "senior" | "unknown"; // Inferido

  // Depuración
  raw_response: object;            // Respuesta original completa de la API
}
```

**Reglas de normalización por fuente:**

| Campo NormalizedJob | JSearch → campo | SerpAPI → campo |
|--------------------|-----------------|-----------------|
| `job_id` | `job_id` | Hash de `title + company + location` |
| `job_title` | `job_title` | `title` |
| `company_name` | `employer_name` | `company_name` |
| `location_city` | `job_city` | Extraído de `location` |
| `location_country` | `job_country` | Extraído de `location` |
| `is_remote` | `job_is_remote` | `detected_extensions.work_from_home` |
| `salary_min` | `job_min_salary` | Parseado de `detected_extensions.salary` |
| `salary_max` | `job_max_salary` | Parseado de `detected_extensions.salary` |
| `salary_currency` | `job_salary_currency` | Inferido de moneda en `detected_extensions.salary` |
| `description_raw` | `job_description` | `description` |
| `qualifications_raw` | `[]` | `job_highlights.Qualifications` |
| `posted_at` | `job_posted_at_datetime_utc` | `detected_extensions.posted_at` |
| `apply_url` | `job_apply_link` | `apply_options[0].link` |

---

## 5. Construcción de Queries desde StudentProfile

El `QueryBuilder` traduce un `StudentProfile` a los parámetros de cada API.

### Algoritmo de construcción de query

```python
def build_query_term(profile: StudentProfile) -> str:
    """
    Combina seniority + rol preferido + tecnología primaria.
    Ordena por popularidad en bolsas LATAM.
    """
    seniority_term = "junior"  # siempre para Lyfter MVP
    role = profile.preferences.roles[0]  # primer rol preferido
    tech = profile.stack.primary[0]     # primera tecnología primaria

    return f"{seniority_term} {role} {tech}"
    # Ejemplo: "junior Frontend Developer React"


def build_jsearch_params(profile: StudentProfile) -> dict:
    return {
        "query": build_query_term(profile),
        "location": profile.location.country,
        "remote_jobs_only": profile.modality == ["remote"],
        "date_posted": "month",
        "num_pages": 2
    }


def build_serpapi_params(profile: StudentProfile) -> dict:
    country_gl_map = {"Costa Rica": "cr", "Mexico": "mx", "Colombia": "co", "Argentina": "ar"}
    return {
        "engine": "google_jobs",
        "q": build_query_term(profile),
        "location": profile.location.country,
        "gl": country_gl_map.get(profile.location.country, "cr"),
        "hl": "es",
        "chips": "date_posted:month",
    }
```

---

## 6. Pruebas de Consultas con Perfiles de Ejemplo

### Test 1 — JSearch con Valentina Torres (`lyfter-001`)

**Perfil:** Junior Frontend Developer, React/JS, San José CR, remoto o híbrido.

**Query construida:**
```python
# build_jsearch_params(valentina)
{
    "query": "junior Frontend Developer React",
    "location": "Costa Rica",
    "remote_jobs_only": False,  # acepta híbrido
    "date_posted": "month",
    "num_pages": 2
}
```

**Respuesta esperada (estructura):**
```json
{
  "data": [
    {
      "job_id": "abc123",
      "employer_name": "TechCo CR",
      "job_title": "Junior Frontend Developer",
      "job_city": "San José",
      "job_country": "CR",
      "job_is_remote": true,
      "job_description": "Buscamos desarrollador frontend junior con experiencia en React y JavaScript...",
      "job_min_salary": null,
      "job_max_salary": null,
      "job_salary_currency": null,
      "job_apply_link": "https://example.com/apply/abc123",
      "job_posted_at_datetime_utc": "2026-05-20T10:00:00Z"
    }
  ]
}
```

**Normalización resultante:**
```json
{
  "job_id": "abc123",
  "source": "jsearch",
  "job_title": "Junior Frontend Developer",
  "company_name": "TechCo CR",
  "location_city": "San José",
  "location_country": "CR",
  "is_remote": true,
  "modality": ["remote"],
  "salary_min": null,
  "salary_max": null,
  "salary_currency": null,
  "description_raw": "Buscamos desarrollador frontend junior con experiencia en React y JavaScript...",
  "qualifications_raw": [],
  "stack_keywords": ["React", "JavaScript"],
  "seniority_signal": "junior",
  "apply_url": "https://example.com/apply/abc123",
  "posted_at": "2026-05-20T10:00:00Z"
}
```

**Hard filter check para Valentina:**
- `is_remote = true` → pasa (modality acepta remote)
- `salary_min = null` → no se aplica filtro de salario mínimo (dato ausente)
- `location_country = "CR"` → pasa (no tiene excluded_locations)

**Score parcial (stack match):**
- `description_raw` contiene "React" ✅ y "JavaScript" ✅
- `stack_keywords`: ["React", "JavaScript"] vs. primary: ["React", "JavaScript", "HTML", "CSS"] → 2/4 = 50% → 17.5/35 pts base

**Criterios de aceptación del test:**
- ✅ Devuelve al menos 5 resultados para Costa Rica
- ✅ Al menos 2 resultados contienen "React" en description_raw
- ✅ Al menos 1 resultado con `job_is_remote = true`
- ⚠️ Tasa de salario esperada: <25% de resultados con salary_min no-null

---

### Test 2 — SerpAPI con Andrés Mejía (`lyfter-002`)

**Perfil:** Junior Backend/Fullstack, Node.js/PostgreSQL, Heredia CR, cualquier modalidad, solo CR.

**Query construida:**
```python
# build_serpapi_params(andres)
{
    "engine": "google_jobs",
    "q": "junior Backend Developer Node.js",
    "location": "Costa Rica",
    "gl": "cr",
    "hl": "es",
    "chips": "date_posted:month"
}
```

**Respuesta esperada (estructura):**
```json
{
  "jobs_results": [
    {
      "title": "Desarrollador Backend Junior",
      "company_name": "Startup Tica",
      "location": "Heredia, Costa Rica",
      "via": "LinkedIn",
      "description": "Buscamos desarrollador backend con Node.js y PostgreSQL...",
      "job_highlights": {
        "Qualifications": ["1 año de experiencia en Node.js", "PostgreSQL", "REST APIs", "Git"],
        "Benefits": ["Trabajo remoto", "Seguro médico"]
      },
      "apply_options": [{"link": "https://linkedin.com/jobs/xyz"}],
      "detected_extensions": {
        "posted_at": "hace 3 días",
        "work_from_home": false,
        "salary": "₡750,000 – ₡1,100,000 al mes"
      }
    }
  ]
}
```

**Normalización resultante:**
```json
{
  "job_id": "hash-startup-tica-backend-heredia",
  "source": "serpapi",
  "job_title": "Desarrollador Backend Junior",
  "company_name": "Startup Tica",
  "location_city": "Heredia",
  "location_country": "Costa Rica",
  "is_remote": false,
  "modality": ["on-site"],
  "salary_min": 750000,
  "salary_max": 1100000,
  "salary_currency": "CRC",
  "salary_period": "monthly",
  "description_raw": "Buscamos desarrollador backend con Node.js y PostgreSQL...",
  "qualifications_raw": ["1 año de experiencia en Node.js", "PostgreSQL", "REST APIs", "Git"],
  "stack_keywords": ["Node.js", "PostgreSQL", "REST APIs", "Git"],
  "seniority_signal": "junior",
  "apply_url": "https://linkedin.com/jobs/xyz",
  "posted_at": "2026-05-22"
}
```

**Hard filter check para Andrés:**
- `location_country = "Costa Rica"` → pasa (excluded_locations: ["outside Costa Rica"])
- `is_remote = false, modality = ["on-site"]` → pasa (Andrés acepta on-site)
- `salary_min = 750000 CRC` → pasa (min_salary = 750000 CRC, exactamente en el límite)

**Score parcial (stack match):**
- `qualifications_raw` contiene "Node.js" ✅, "PostgreSQL" ✅, "REST APIs" ✅, "Git" ✅
- 4/4 de primary skills detectadas → 35/35 pts base de stack match (antes de ajuste de growth_priority)
- `growth_priority = "stability"` → si empresa es mid-size o enterprise, +10 pts en company_size

**Criterios de aceptación del test:**
- ✅ `gl=cr` restringe resultados a Costa Rica — 0 resultados de fuera del país
- ✅ `qualifications_raw` no vacío en al menos 50% de resultados
- ✅ Al menos 1 resultado con salario en CRC en `detected_extensions.salary`
- ✅ Resultados en español gracias a `hl=es`

---

## 7. Recomendación MVP

| Fase | Fuente | Costo | Capacidad |
|------|--------|-------|-----------|
| **Spike / validación** (POC) | JSearch free + SerpAPI free | $0/mes | 200 req + 100 búsquedas/mes |
| **MVP — cohort <30 estudiantes** | JSearch Pro | $25/mes | 10,000 req/mes = ~333 req/día |
| **Escala — cohort >50 estudiantes** | SerpAPI Developer | $75/mes | 5,000 búsquedas/mes = ~160/día |
| **Expansión LATAM (MX/BR)** | Adzuna (complemento) | A consultar | Salario estructurado para MX/BR |

**Fuente MVP recomendada: JSearch Pro**

Razones:
1. Costa Rica cubierta vía Google for Jobs (Computrabajo CR, LinkedIn CR, Indeed CR)
2. Free tier permite validar la hipótesis de cobertura sin costo
3. API más simple de integrar (menos parámetros que SerpAPI)
4. Con cache de 24h por query, 10,000 req/mes son suficientes para 30 estudiantes con refresh diario
5. El campo `description_raw` contiene suficiente señal para el LLM (`ExtractJobSignals`)

**Trigger para migrar a SerpAPI:**
- Cobertura CR <5 resultados relevantes por perfil con JSearch
- Cohort supera 50 estudiantes y el rate limit de JSearch Pro no alcanza
- Se necesita expansión a más de 2 países LATAM simultáneamente

---

## 8. Restricciones de Implementación

1. **Cache obligatorio:** cada query debe cachearse por 24 horas. La misma query no puede consumir rate limit dos veces en el mismo día.
2. **Sin scraping directo:** el agente solo puede usar APIs que gestionen la relación con el sitio fuente (JSearch, SerpAPI). Está prohibido usar JobSpy o cualquier scraper que viole ToS.
3. **Freshness mínima:** `date_posted: "month"` es el máximo. Ofertas de más de 30 días no se procesan.
4. **Deduplicación:** si el mismo `job_id` aparece en múltiples fuentes, se conserva solo la instancia con más campos completos.
5. **NormalizedJob como único contrato:** el `ScoringEngine` nunca consume respuestas raw de API — solo `NormalizedJob` objects.

---

## 9. Variables de Entorno Requeridas

```bash
JSEARCH_API_KEY=          # Obtenida de rapidapi.com (sin tarjeta en free tier)
SERPAPI_API_KEY=          # Obtenida de serpapi.com (100 búsquedas gratuitas)
JOB_CACHE_TTL_SECONDS=86400  # 24 horas
```

---

## 10. Próximos Pasos

1. Obtener `JSEARCH_API_KEY` en `rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch`
2. Obtener `SERPAPI_API_KEY` en `serpapi.com`
3. Ejecutar test real con `fixtures/profiles/junior_frontend.json` (Valentina) y validar criterios del Test 1
4. Ejecutar test real con `fixtures/profiles/junior_fullstack.json` (Andrés) y validar criterios del Test 2
5. Si ambos tests pasan criterios de aceptación → implementar `JobFetcher` con JSearch como fuente primaria
6. Si cobertura CR <5 resultados → migrar a SerpAPI como fuente primaria
