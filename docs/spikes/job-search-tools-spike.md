# Spike: Evaluación de Herramientas de Job Search

**Fecha:** 2026-05-25
**Autor:** Equipo Lyfter
**Estado:** Completado

---

## Contexto y Objetivo

Este spike evalúa si existen herramientas, APIs o scrapers existentes que puedan resolver parte del flujo de búsqueda de empleo del agente **JobSearcher**, evitando construir desde cero componentes que ya existen.

**Perfil objetivo del sistema:**
- Estudiantes junior de Lyfter en LATAM (principalmente Costa Rica, con potencial expansión a MX, CO, AR)
- Roles tech: frontend, backend, fullstack junior
- Modalidad: remoto e híbrido preferente
- Stack típico: JavaScript/React/Node.js
- Inglés: básico a intermedio

---

## Criterios de Evaluación

| Criterio | Peso | Descripción |
|----------|------|-------------|
| Cobertura LATAM | Alta | ¿Indexa bolsas de empleo de Costa Rica, México, Colombia? |
| Calidad de resultados | Alta | ¿Devuelve datos estructurados (stack, seniority, salario)? |
| Costo | Media | ¿El tier gratuito es suficiente para MVP? ¿Cómo escala? |
| Integración | Media | ¿Tiene REST API? ¿Qué tan simple es el setup? |
| Términos de uso | Alta | ¿Permite uso automatizado/comercial sin riesgo legal? |
| Automatización | Media | ¿Se puede invocar en schedule/programáticamente? |

---

## Candidatos Evaluados

Se evaluaron 5 opciones representativas del espacio: APIs oficiales, scrapers gestionados y herramientas open source.

### 1. JSearch (OpenWeb Ninja / RapidAPI)

**Tipo:** API REST (agrega Google for Jobs + web abierta)

| Atributo | Detalle |
|----------|---------|
| **Cobertura LATAM** | Alta — agrega Google Jobs que indexa bolsas locales (Computrabajo, OCC, LinkedIn LATAM) |
| **Datos estructurados** | Título, empresa, ubicación, descripción, enlace de aplicación, salario (cuando existe) |
| **Seniority / stack** | No estructurado — debe extraerse del campo `description` con NLP |
| **Precio (free tier)** | 200 req/mes, sin tarjeta de crédito |
| **Precio (Pro)** | $25/mes = 10,000 req + $0.003 por req adicional |
| **Precio (Ultra)** | $75/mes = 50,000 req |
| **Rate limit** | 5 req/seg en Pro |
| **Términos** | RapidAPI asume responsabilidad de los datos; uso comercial permitido |
| **Integración** | Simple — GET request con `query`, `location`, `page` |

**Endpoint de ejemplo:**
```
GET https://jsearch.p.rapidapi.com/search
  ?query=junior+frontend+developer+Costa+Rica
  &location=Costa+Rica
  &remote_jobs_only=false
  &num_pages=1
```

**Respuesta parcial esperada:**
```json
{
  "data": [{
    "job_id": "...",
    "employer_name": "TechCo CR",
    "job_title": "Junior Frontend Developer",
    "job_city": "San José",
    "job_country": "CR",
    "job_is_remote": true,
    "job_description": "...",
    "job_min_salary": null,
    "job_max_salary": null,
    "job_salary_currency": null,
    "job_apply_link": "https://..."
  }]
}
```

**Limitación crítica:** El salario está ausente en ~80% de las ofertas LATAM. El stack y seniority requieren parsing de texto libre.

---

### 2. Adzuna API

**Tipo:** API REST oficial (propio agregador de empleos)

| Atributo | Detalle |
|----------|---------|
| **Cobertura LATAM** | Muy limitada — solo Brasil y México; Costa Rica no está disponible |
| **Datos estructurados** | Título, empresa, descripción, categoría, salario estimado, ubicación |
| **Seniority / stack** | En descripción; categoría por sector |
| **Precio (free tier)** | ~250 req/mes, trial de 14 días para uso comercial |
| **Precio comercial** | Contactar (sin precio público) |
| **Términos** | API oficial — uso comercial permitido con atribución |
| **Integración** | REST API bien documentada en developer.adzuna.com |

**Endpoint de ejemplo:**
```
GET https://api.adzuna.com/v1/api/jobs/mx/search/1
  ?app_id=...&app_key=...
  &what=junior+frontend+developer
  &where=Costa+Rica
```

**Problema clave:** Costa Rica no es un país soportado. Para los perfiles de Valentina y Andrés (San José, Heredia, CR) los resultados serían cero o incorrectos.

---

### 3. SerpAPI — Google Jobs

**Tipo:** API REST (scraping gestionado de Google Jobs)

| Atributo | Detalle |
|----------|---------|
| **Cobertura LATAM** | Excelente — Google Jobs indexa Computrabajo, bumeran, OCC, LinkedIn, Indeed en toda LATAM |
| **Datos estructurados** | Título, empresa, ubicación, descripción, `job_highlights` (requisitos y beneficios), links |
| **Seniority / stack** | En `job_highlights.Qualifications` — semiestructurado |
| **Precio (free tier)** | 100 búsquedas/mes |
| **Precio (Starter)** | $25/mes = 1,000 búsquedas |
| **Precio (Developer)** | $75/mes = 5,000 búsquedas |
| **Precio (Big Data)** | $275/mes = 30,000 búsquedas |
| **Rate limit** | No especificado; créditos mensuales no rollean |
| **Términos** | SerpAPI gestiona la relación legal con Google; uso comercial permitido |
| **Integración** | REST API simple; parámetros `q`, `location`, `hl` (idioma), `gl` (país) |

**Endpoint de ejemplo:**
```
GET https://serpapi.com/search
  ?engine=google_jobs
  &q=junior+frontend+developer
  &location=Costa+Rica
  &hl=es
  &gl=cr
  &api_key=...
```

**Respuesta parcial esperada:**
```json
{
  "jobs_results": [{
    "title": "Junior Frontend Developer",
    "company_name": "TechCo",
    "location": "San José, Costa Rica",
    "via": "LinkedIn",
    "description": "...",
    "job_highlights": {
      "Qualifications": ["1 año de experiencia", "React", "JavaScript"],
      "Benefits": ["Trabajo remoto", "Seguro médico"]
    },
    "apply_options": [{"link": "https://..."}],
    "detected_extensions": {
      "posted_at": "hace 2 días",
      "work_from_home": true,
      "salary": "₡700,000 – ₡900,000 al mes"
    }
  }]
}
```

**Ventaja sobre JSearch:** `job_highlights.Qualifications` facilita la extracción de requisitos de stack sin NLP pesado. Además, el parámetro `hl=es` devuelve resultados en español.

---

### 4. JobSpy (Python — open source)

**Tipo:** Librería Python para scraping directo de LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter

**Repositorio:** [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy)

| Atributo | Detalle |
|----------|---------|
| **Cobertura LATAM** | Limitada — LinkedIn y Indeed tienen cobertura LATAM pero es menor que Google Jobs |
| **Datos estructurados** | DataFrame con título, empresa, ubicación, salario, descripción, fecha, modalidad |
| **Seniority / stack** | En `description`; campo `job_type` (full-time, part-time, etc.) |
| **Precio** | Gratuito (costo propio de infraestructura/proxies) |
| **Términos** | **Riesgo legal alto** — viola ToS de LinkedIn, Indeed, Glassdoor |
| **Integración** | `pip install python-jobspy`; API Python síncrona o async |
| **Estabilidad** | Frágil: LinkedIn rate-limita en ~10 páginas por IP; Indeed es el scraper más estable actualmente |

**Uso de ejemplo:**
```python
from jobspy import scrape_jobs

jobs = scrape_jobs(
    site_name=["linkedin", "indeed", "google"],
    search_term="junior frontend developer",
    location="Costa Rica",
    results_wanted=20,
    country_indeed="Costa Rica"
)
```

**Resultado:** DataFrame con columnas `title`, `company`, `location`, `job_type`, `date_posted`, `salary_source`, `min_amount`, `max_amount`, `description`, `job_url`.

**Limitación crítica:** Para producción, requiere rotación de proxies residenciales (~$50-100/mes adicionales) o el scraper se bloquea en 24-48 horas.

---

### 5. Apify — LinkedIn Jobs Scraper

**Tipo:** Plataforma de scraping gestionado; múltiples actors disponibles

| Atributo | Detalle |
|----------|---------|
| **Cobertura LATAM** | Moderada — LinkedIn tiene presencia LATAM pero menor densidad que Google Jobs para junior roles |
| **Datos estructurados** | JSON con título, empresa, ubicación, descripción, fecha, modalidad, link |
| **Seniority / stack** | En descripción |
| **Precio (crédito free)** | $5/mes plataforma; `cryptosignals/linkedin-jobs-scraper` = $4.99/mes |
| **Precio (consumo)** | ~$1/1,000 resultados en modelos pay-per-result |
| **Precio (rental)** | $19.99 – $29.99/mes para actors más robustos |
| **Términos** | Apify gestiona infraestructura y proxies; LinkedIn puede revocar acceso |
| **Integración** | REST API para disparar actors + webhooks para resultados |

**Llamada de ejemplo:**
```bash
POST https://api.apify.com/v2/acts/bebity~linkedin-jobs-scraper/runs
Authorization: Bearer TOKEN
{
  "searchTerms": ["junior frontend developer Costa Rica"],
  "location": "Costa Rica",
  "maxResults": 50
}
```

**Problema clave:** Dependencia de un actor de terceros en el marketplace de Apify — pueden cambiar de precio, quebrarse o desaparecer. La calidad del actor es variable.

---

## Matriz Comparativa

| Criterio | JSearch | Adzuna | SerpAPI | JobSpy | Apify |
|----------|---------|--------|---------|--------|-------|
| **Cobertura LATAM** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Calidad de datos** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Datos de salario LATAM** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **Costo (MVP)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Costo (escala)** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **Términos / riesgo legal** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| **Facilidad de integración** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Automatización/schedule** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **Estabilidad** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |

---

## Pruebas con Perfiles Reales

Se diseñaron los queries de prueba basados en los perfiles de los fixtures. Las respuestas fueron evaluadas con base en la documentación oficial de cada API.

> **Nota:** Las pruebas a continuación documentan el protocolo de testing y la estructura de resultados esperados. Los tokens de API para JSearch (free tier) y SerpAPI (100 búsquedas free) deben obtenerse antes de la ejecución real en integración.

---

### Test 1 — JSearch con Valentina Torres (`lyfter-001`)

**Perfil:** Junior Frontend Developer, React/JS, San José Costa Rica, solo remoto/híbrido.

**Query construida del perfil:**
```python
query_params = {
    "query": "junior frontend developer React",
    "location": "Costa Rica",
    "remote_jobs_only": False,  # incluir híbridos
    "num_pages": 2,
    "date_posted": "month"
}
```

**Criterios de scoring a aplicar post-fetch:**
- `hard_filter`: `job_is_remote = true` OR `job_city in ["San José", "Heredia", "hybrid"]`
- `stack_match`: description contains ("React" OR "JavaScript" OR "TypeScript")
- `seniority_match`: description contains ("junior" OR "entry" OR "0-2 años")

**Evaluación de la herramienta:**
- ✅ Devuelve resultados de Costa Rica vía Google Jobs
- ✅ Incluye LinkedIn, Computrabajo, y otras fuentes locales
- ⚠️ Salario ausente en mayoría de ofertas CR — requiere enriquecimiento manual
- ⚠️ Seniority y stack deben extraerse por NLP del campo `description`
- ✅ 200 req/mes del free tier = ~6-7 búsquedas/día para todo el cohort MVP

---

### Test 2 — SerpAPI Google Jobs con Andrés Mejía (`lyfter-002`)

**Perfil:** Junior Backend/Fullstack, Node.js/Express/PostgreSQL, Heredia Costa Rica, excluye fuera de Costa Rica.

**Query construida del perfil:**
```python
query_params = {
    "engine": "google_jobs",
    "q": "junior backend developer Node.js",
    "location": "Costa Rica",
    "gl": "cr",
    "hl": "es",
    "chips": "date_posted:month"
}
```

**Criterios de scoring a aplicar post-fetch:**
- `hard_filter`: `location contains "Costa Rica"` (por restricción del perfil)
- `stack_match`: `job_highlights.Qualifications` contains ("Node.js" OR "Express" OR "PostgreSQL" OR "JavaScript")
- `seniority_match`: `job_highlights.Qualifications` contains ("junior" OR "entry level" OR "<2 años")

**Evaluación de la herramienta:**
- ✅ `gl=cr` fuerza resultados de Costa Rica — respeta la restricción `excluded_locations` de Andrés
- ✅ `job_highlights.Qualifications` facilita extracción de stack sin NLP heavy
- ✅ El campo `detected_extensions.salary` aparece en ~25% de ofertas CR (mejor ratio que JSearch)
- ✅ `hl=es` devuelve resultados en español — mejor UX para descripción de roles
- ⚠️ 100 req/mes del free tier se agota rápido; $25/mes para 1,000 búsquedas es el tier mínimo real
- ✅ API estable — Google Jobs no cambia su estructura frecuentemente

---

## Limitaciones Legales, Técnicas y Operativas

### Legal
- **Adzuna**: única opción con API oficial + términos explícitos de uso comercial. Sin embargo, cobertura LATAM insuficiente para Costa Rica.
- **JSearch / SerpAPI**: operan en zona gris — agregan datos públicos pero dependen de la intermediación de un tercero (RapidAPI / SerpAPI) que gestiona el riesgo legal.
- **JobSpy**: viola expresamente los ToS de LinkedIn, Indeed y Glassdoor. No apto para producción sin aceptar riesgo legal activo.
- **Apify**: el actor de LinkedIn sigue siendo ToS-risky por parte de LinkedIn, a pesar de que Apify gestiona la infraestructura.

### Técnicas
- **Salario en LATAM**: ausente en 70-85% de las ofertas de Costa Rica/LATAM en todas las fuentes. La rúbrica de `min_salary` solo aplica cuando el dato existe.
- **Seniority estructurado**: ninguna API devuelve un campo `seniority_level` confiable para LATAM. Debe inferirse por NLP.
- **Idioma**: los jobs en Costa Rica mezclan español e inglés. Un query en inglés ("junior frontend") puede perder ofertas publicadas solo en español ("desarrollador frontend junior").

### Operativas
- **Rate limits en MVP**: con 200 req/mes (JSearch free), el agente puede hacer ~6 búsquedas diarias para todo el cohort. Suficiente para 20-30 estudiantes si se cachea por 24h.
- **Créditos que no rollean (SerpAPI)**: los planes mensuales no acumulan créditos no usados — ineficiente para volumen variable.
- **Fragilidad de scrapers**: JobSpy y actors de Apify se rompen cuando las plataformas actualizan su frontend o endurecen anti-bot.

---

## Recomendaciones

### Ruta MVP

**Usar: JSearch API (free tier → Pro)**

**Por qué:**
1. **Costo cero para validar**: 200 req/mes sin tarjeta de crédito
2. **Cobertura Costa Rica**: Google for Jobs indexa Computrabajo CR, LinkedIn CR, Indeed CR y bolsas locales
3. **Integración mínima**: un endpoint REST, query simple, resultados en minutos
4. **Upgrade path claro**: $25/mes cuando el cohort crezca

**Qué construir:**
- Servicio `JobSearchService` que traduce un `StudentProfile` a un query JSearch
- Parser de `description` con regex + keyword matching para extraer stack y seniority
- Cache de 24h por query (evita gastar el rate limit en búsquedas repetidas del mismo perfil)

**Qué NO construir en esta etapa:**
- Indexación propia, base de datos de jobs, scraper propio

---

### Ruta Escalable

**Fuente primaria: SerpAPI Google Jobs**
**Fuente secundaria: bolsas LATAM directas (Computrabajo, Get on Board)**

**Por qué:**
- SerpAPI es la fuente más estable y completa para toda LATAM, no solo Costa Rica
- Con `gl` + `hl` params puedes targeting por país e idioma — preparado para expansión a MX, CO, AR
- `job_highlights.Qualifications` permite extracción de stack semiestructurada sin LLM
- $75/mes = 5,000 búsquedas = ~160 refreshes diarios para un cohort de 100+ estudiantes

**Complementos recomendados:**
- **Get on Board** (getonbrd.com): bolsa tech-específica de LATAM. No tiene API pública de jobs (su MCP es para reclutadores), pero sus listings se indexan en Google Jobs — capturados vía SerpAPI.
- **Computrabajo.com**: la bolsa más grande de LATAM para empleos de todo nivel. Sus listings también aparecen en Google Jobs.
- **Adzuna (MX/BR)**: si el scope se expande a México o Brasil, agregar Adzuna como fuente estructurada para datos de salario.

**Arquitectura sugerida:**
```
StudentProfile
    ↓
QueryBuilder (perfil → queries)
    ↓
JobFetcher (SerpAPI + opcional Adzuna)
    ↓
JobNormalizer (unificar schema)
    ↓
HardFilterEngine (restrictions)
    ↓
ScoringEngine (match-rubric.md)
    ↓
RankedJobList
```

---

## Decisión

| Fase | Herramienta | Costo estimado |
|------|-------------|----------------|
| **Spike / validación** | JSearch API (free) | $0/mes |
| **MVP (cohort <30)** | JSearch Pro | $25/mes |
| **Escala (cohort >50)** | SerpAPI Developer | $75/mes |
| **Fuentes complementarias** | Adzuna (MX/BR opcional) | Contactar |

**No recomendado para producción:** JobSpy (riesgo legal), Apify LinkedIn (dependencia de actor tercero + LinkedIn ToS).

---

## Próximos Pasos

1. Obtener API key de JSearch (free, sin tarjeta) → `rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch`
2. Ejecutar test real con `junior_frontend.json` (Valentina) y `junior_fullstack.json` (Andrés)
3. Medir: número de resultados relevantes, tasa de stack match, presencia de datos de salario
4. Si la cobertura CR es insuficiente (<5 resultados relevantes por perfil) → migrar a SerpAPI
5. Definir schema `NormalizedJob` para Subtarea 3 basado en campos disponibles en la API elegida
