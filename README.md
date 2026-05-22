# JobSearcher — Agente Autónomo de Búsqueda de Empleo

## Índice

1. [Visión General](#1-visión-general)
2. [Stack Tecnológico](#2-stack-tecnológico)
3. [Arquitectura](#3-arquitectura)
4. [Fuentes de Datos](#4-fuentes-de-datos)
5. [Plan de Trabajo](#5-plan-de-trabajo)
   - [5.1 Definir perfil del candidato y criterios de match](#subtarea-1--definir-perfil-del-candidato-y-criterios-de-match)
   - [5.2 Spike de soluciones existentes](#subtarea-2--spike-de-soluciones-existentes-para-búsqueda-de-empleo)
   - [5.3 Evaluar frameworks de orquestación](#subtarea-3--evaluar-frameworks-de-orquestación-completada-se-eligió-hermes)
   - [5.4 Spike de APIs y fuentes de datos](#subtarea-4--spike-de-apis-y-fuentes-para-obtener-oportunidades-laborales)
   - [5.5 Diseñar pipeline ETL](#subtarea-5--diseñar-pipeline-de-ingesta-normalización-y-almacenamiento)
   - [5.6 Implementar POC de ingesta](#subtarea-6--implementar-poc-de-ingesta-de-oportunidades-laborales)
   - [5.7 Implementar scoring y curación](#subtarea-7--implementar-scoring-y-curación-de-oportunidades)
   - [5.8 Definir flujo de entrega y feedback](#subtarea-8--definir-flujo-de-entrega-y-feedback-para-recomendaciones)
6. [Decisiones Pendientes](#6-decisiones-pendientes)
7. [Criterios de Aceptación](#7-criterios-de-aceptación)

---

## 1. Visión General

**JobSearcher** es un agente autónomo de búsqueda de empleo capaz de:

- Recibir y gestionar perfiles de múltiples candidatos.
- Procesar oportunidades laborales desde diversas fuentes (LinkedIn, Indeed, Glassdoor, InfoJobs, scraping de portales públicos).
- Normalizar, almacenar y puntuar las oportunidades según criterios de match por candidato.
- Entregar recomendaciones personalizadas vía API / Webhook.

El sistema es **multi-usuario**: cada candidato tiene su propio perfil con criterios de match independientes.

---

## 2. Stack Tecnológico

| Capa                                     | Tecnología                                       |
| ---------------------------------------- | ------------------------------------------------ |
| **Backend / ML / Scraping**              | Python                                           |
| **Orquestación / Integraciones**         | TypeScript                                       |
| **Framework de orquestación del agente** | Hermes                                           |
| **Almacenamiento**                       | Por definir (ver [D4](#6-decisiones-pendientes)) |
| **Canal de entrega**                     | API                                              |

---

## 3. Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                   Capa de Orquestación                  │
│                        (Hermes)                         │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   ┌──────────┐   ┌──────────────┐  ┌────────────────┐
   │ Ingesta  │   │  Scoring &   │  │  Entrega de    │
   │ de datos │   │  Curación    │  │Recomendaciones │
   └─────┬────┘   └──────┬───────┘  └───────┬────────┘
         │                │                  │
   LinkedIn API     Modelo de match    API / Webhook
   Indeed           por candidato      (REST endpoint
   Glassdoor        (multi-perfil)      o webhook)
   InfoJobs
   Scraping
         │
   ┌─────▼──────────────────────┐
   │  Pipeline de Normalización │
   │  y Almacenamiento          │
   └────────────────────────────┘
```

> ⚠️ La arquitectura final puede ajustarse según los resultados de los spikes técnicos (Subtareas 2, 3 y 4).

---

## 4. Fuentes de Datos

| Fuente        | Tipo de Acceso                  | Estado         | Consideraciones                                                                                                |
| ------------- | ------------------------------- | -------------- | -------------------------------------------------------------------------------------------------------------- |
| **LinkedIn**  | API oficial (LinkedIn Jobs API) | ⚠️ No iniciado | Requiere aprobación de LinkedIn; rate limits estrictos; puede requerir cuenta de empresa. **Gestión urgente.** |
| **Indeed**    | API / RSS feed                  | Por validar    | Indeed tiene API para publishers; también ofrece RSS                                                           |
| **Glassdoor** | Scraping / API oficial          | Por validar    | API requiere aprobación; enfocada en reviews + salarios + ofertas                                              |
| **InfoJobs**  | Scraping                        | Por validar    | Portal popular en España y Latinoamérica                                                                       |

> ⚠️ Para LinkedIn se necesitan credenciales/aprobaciones que deben gestionarse con urgencia antes del spike de APIs (Subtarea 4).

---

## 5. Plan de Trabajo

### Subtarea 1 — Definir perfil del candidato y criterios de match

**Objetivo:** Establecer el modelo de datos del candidato y la lógica de matching.

**Dependencias:** Ninguna

**Actividades:**

- Definir el esquema del perfil de candidato (campos mínimos y opcionales): nombre, cargo buscado, industrias de interés, nivel de seniority, modalidad de trabajo (presencial / remoto / híbrido), ubicación preferida, rango salarial esperado, idiomas, habilidades técnicas y blandas, disponibilidad, estado de búsqueda (activo / pasivo).
- Identificar los criterios de match y asignar un peso relativo a cada uno (p. ej., cargo 30 %, industria 20 %, modalidad 15 %, ubicación 15 %, salario 10 %, idioma 10 %).
- Definir el rango de scoring final (0–100) y el umbral mínimo de relevancia configurable por candidato.
- Documentar el modelo en formato JSON Schema o equivalente.
- Crear al menos 2 perfiles de candidato ficticios con distintos criterios para usar como fixtures de prueba a lo largo del proyecto.

**Entregables:**

- Esquema JSON del perfil de candidato (`candidate_profile.schema.json`).
- Documento `scoring_logic.md` con la tabla de criterios, pesos y fórmula de cálculo.
- Directorio `fixtures/` con mínimo 2 perfiles de ejemplo en JSON.

**Riesgos y consideraciones:**

- Los pesos iniciales son hipótesis; se revisarán una vez que haya datos reales de scoring (Subtarea 7).
- El esquema debe ser lo suficientemente flexible para incorporar criterios nuevos sin migraciones costosas.
- Acordar desde el principio si los campos opcionales ausentes neutralizan el criterio (peso 0) o penalizan el score.

**Criterios de aceptación:**

- [ ] El esquema soporta múltiples candidatos simultáneos.
- [ ] Todos los criterios de match están documentados con su peso relativo.
- [ ] El modelo es extensible sin romper la estructura existente.
- [ ] Los 2 perfiles de fixtures son usables directamente en los tests de Subtareas 6 y 7.

---

### Subtarea 2 — Spike de soluciones existentes para búsqueda de empleo

**Objetivo:** Investigar herramientas, agentes y librerías existentes para no reinventar la rueda.

**Dependencias:** Ninguna

**Actividades:**

- Relevar proyectos open source de agentes de búsqueda de empleo (GitHub, HuggingFace, PyPI).
- Evaluar librerías de scraping de ofertas laborales (jobspy, job-scraper, etc.).
- Evaluar wrappers de APIs de empleo ya existentes.
- Para cada solución relevada: anotar lenguaje, licencia, nivel de mantenimiento, qué problema resuelve y limitaciones.
- Identificar qué componentes o patrones son directamente reutilizables en este proyecto.

**Entregables:**

- Informe `research/existing_solutions.md` con tabla comparativa de mínimo 5 herramientas.
- Recomendación explícita sobre qué adoptar, adaptar o descartar, con justificación.

**Riesgos y consideraciones:**

- Priorizar soluciones con licencia permisiva (MIT, Apache 2.0); evitar GPL si el proyecto puede ser comercial.
- Un proyecto abandonado puede ser útil como referencia de arquitectura aunque no se adopte directamente.
- El tiempo invertido aquí impacta directamente en la Subtarea 6: una buena librería de scraping puede ahorrar semanas de desarrollo.

**Criterios de aceptación:**

- [ ] Se relevaron al menos 5 proyectos/herramientas existentes.
- [ ] Se identificaron al menos 2 componentes o patrones reutilizables.
- [ ] El informe incluye links y referencias verificables.
- [ ] Cada herramienta evaluada tiene anotada su licencia y estado de mantenimiento.

---

### Subtarea 3 — Evaluar frameworks de orquestación _(completada: se eligió Hermes)_

**Objetivo:** Seleccionar el framework de orquestación del agente con base en evidencia.

**Dependencias:** Ninguna.

**Estado:** Decisión tomada — **Hermes**.

**Actividades realizadas:**

- Comparación entre OpenClaw y Hermes sobre criterios de: madurez, ecosistema, facilidad de integración con Python/TypeScript, soporte de tareas paralelas, documentación y comunidad.
- Construcción de un prototipo mínimo con cada framework para validar la experiencia de desarrollo.
- Revisión del resultado con el equipo y aprobación de la elección.

**Entregables pendientes de formalizar:**

- Tabla comparativa completa (OpenClaw vs Hermes) en `research/frameworks_comparison.md`.
- Código de los prototipos mínimos de ambos frameworks en `spikes/frameworks/`.
- ADR (Architecture Decision Record) con la justificación de la elección.

**Riesgos y consideraciones:**

- Aunque la decisión está tomada, formalizar la tabla comparativa y el ADR evita que el razonamiento se pierda y facilita incorporar nuevos miembros al proyecto.
- Si Hermes presenta limitaciones imprevistas durante la implementación, el ADR sirve de punto de partida para evaluar una migración.

**Criterios de aceptación:**

- [ ] Ambos frameworks fueron probados con un caso de uso real.
- [ ] La tabla comparativa cubre todos los criterios definidos.
- [ ] La decisión final está documentada en un ADR aprobado.

---

### Subtarea 4 — Spike de APIs y fuentes para obtener oportunidades laborales

**Objetivo:** Validar el acceso real a las fuentes de datos definidas antes de invertir en implementación.

**Dependencias:** Gestión de credenciales LinkedIn (D6) debe iniciarse en paralelo; idealmente resuelta antes de comenzar esta subtarea.

**Actividades:**

- **LinkedIn:** Solicitar acceso a LinkedIn Jobs API, probar autenticación OAuth 2.0, extraer muestra de ofertas y documentar campos disponibles, rate limits y restricciones de uso.
- **Indeed:** Probar la API para publishers y/o el feed RSS; evaluar viabilidad de scraping como alternativa si la API no es accesible.
- **Glassdoor:** Evaluar disponibilidad de API oficial (requiere aprobación) y scraping como alternativa; verificar si los datos incluyen ofertas o solo reviews/salarios.
- **InfoJobs:** Evaluar scraping del portal; revisar términos de servicio y estructura del HTML/JSON de respuesta.
- Para cada fuente: documentar rate limit, estructura de respuesta, campos disponibles, restricciones legales/ToS y alternativa si el acceso está bloqueado.
- Registrar muestras de datos crudos (`spikes/data_sources/<fuente>/sample_raw.json`).

**Entregables:**

- `research/data_sources_report.md`: reporte por fuente con estado de acceso ✅/❌ + alternativa propuesta.
- Muestras de datos crudos en `spikes/data_sources/`.
- Tabla de mapeo de campos por fuente hacia el esquema normalizado (insumo directo para Subtarea 5).

**Riesgos y consideraciones:**

- LinkedIn es la fuente de mayor valor pero la de acceso más incierto; no bloquear el avance del proyecto si la aprobación demora.
- El scraping puede violar los ToS de algunas plataformas; documentar el análisis legal antes de implementarlo en producción.
- Si una fuente queda bloqueada, identificar un sustituto (ej. Adzuna API, RemoteOK, We Work Remotely) para cumplir el criterio de mínimo 2 fuentes activas.

**Criterios de aceptación:**

- [ ] Al menos 2 fuentes tienen acceso confirmado y datos extraídos.
- [ ] Cada fuente tiene documentado su rate limit y estructura de respuesta.
- [ ] El mapeo de campos hacia el esquema normalizado está completo.
- [ ] Cada fuente bloqueada tiene documentada una alternativa concreta.

---

### Subtarea 5 — Diseñar pipeline de ingesta, normalización y almacenamiento

**Objetivo:** Definir cómo los datos crudos de las fuentes se transforman y persisten antes de implementar.

**Dependencias:** Subtarea 1 (esquema del candidato), Subtarea 4 (estructura de datos por fuente y tabla de mapeo de campos).

**Actividades:**

- Diseñar el flujo completo:
  - **Extract:** conector por fuente (API o scraper), ejecución periódica o bajo demanda.
  - **Transform:** normalización de campos al esquema unificado de oportunidad, limpieza de texto (HTML, caracteres especiales), enriquecimiento (inferir campos faltantes si es posible).
  - **Load:** escritura en el store elegido, manejo de errores y reintentos.
- Definir el esquema de la entidad `JobOpportunity`: título, empresa, descripción, ubicación, modalidad, salario (rango/estimado), fuente, URL, fecha de publicación, fecha de ingesta, hash de deduplicación.
- Diseñar la estrategia de deduplicación: hash sobre campos clave (título + empresa + ubicación) para detectar duplicados entre fuentes o ejecuciones repetidas.
- Resolver la tecnología de almacenamiento (D4) y documentarla en un ADR.
- Definir política de retención de datos (cuánto tiempo se conservan oportunidades vencidas).

**Entregables:**

- Diagrama del pipeline ETL (`docs/etl_pipeline.png` o diagrama ASCII en Markdown).
- Esquema de la entidad `JobOpportunity` en JSON Schema.
- ADR de diseño del pipeline y elección de almacenamiento (`docs/adr/001_storage.md`).

**Riesgos y consideraciones:**

- La elección de almacenamiento (D4) puede cambiar el diseño del pipeline; resolver D4 al inicio de esta subtarea.
- La normalización de salarios es especialmente difícil: distintas fuentes usan rangos, monedas y periodicidades distintas; definir un campo estimado + campo original crudo.
- Diseñar los transformadores como módulos stateless para facilitar el testing unitario.

**Criterios de aceptación:**

- [ ] El pipeline soporta múltiples fuentes de manera modular.
- [ ] Existe una estrategia de deduplicación documentada y reproducible.
- [ ] El esquema de almacenamiento es compatible con el modelo de candidato (Subtarea 1).
- [ ] La decisión de tecnología de almacenamiento (D4) está resuelta y documentada en un ADR.

---

### Subtarea 6 — Implementar POC de ingesta de oportunidades laborales

**Objetivo:** Construir un prototipo funcional que ingeste datos reales de al menos una fuente y los persista en el store.

**Dependencias:** Subtarea 4 (acceso a fuentes validado), Subtarea 5 (diseño del pipeline y esquema de almacenamiento resuelto).

**Actividades:**

- Implementar el conector para la fuente más accesible según el resultado de Subtarea 4.
- Implementar el transformador de esa fuente al esquema normalizado `JobOpportunity`.
- Implementar el módulo de escritura al store elegido, incluyendo deduplicación.
- Ejecutar el pipeline de extremo a extremo sobre datos reales y verificar los resultados.
- Documentar cómo ejecutar el POC localmente (README o `CONTRIBUTING.md`).
- Medir y reportar calidad de los datos: completitud por campo, porcentaje de duplicados detectados, errores de parseo.
- Opcional: agregar un segundo conector si el tiempo lo permite, para validar la modularidad del pipeline.

**Entregables:**

- Código del conector + transformador + escritura al store en `src/ingestion/`.
- Dataset de oportunidades reales almacenado y verificado (mínimo 50 registros).
- `docs/poc_ingestion_report.md`: reporte de calidad de datos (completitud, consistencia, duplicados).
- Instrucciones de ejecución en el README principal o en un documento dedicado.

**Riesgos y consideraciones:**

- Priorizar la fuente con acceso más estable; no bloquear el POC esperando la aprobación de LinkedIn.
- El código del POC no necesita ser production-ready, pero sí modular y testeable para facilitar la Subtarea 7.
- Documentar cualquier workaround o limitación encontrada; serán insumos para Subtarea 4 si hay hallazgos nuevos.

**Criterios de aceptación:**

- [ ] El POC ingesta datos de al menos 1 fuente real con un mínimo de 50 registros.
- [ ] Los datos están normalizados y almacenados según el esquema definido en Subtarea 5.
- [ ] El reporte de calidad de datos está completo (completitud por campo, duplicados, errores).
- [ ] El POC es ejecutable por cualquier miembro del equipo con las instrucciones documentadas.

---

### Subtarea 7 — Implementar scoring y curación de oportunidades

**Objetivo:** Construir el motor de match entre oportunidades y perfiles de candidatos, produciendo un score 0–100 por par (candidato, oportunidad).

**Dependencias:** Subtarea 1 (criterios y pesos de scoring), Subtarea 6 (dataset real disponible en el store).

**Actividades:**

- Implementar el algoritmo de scoring definido en Subtarea 1: calcular score parcial por criterio y score total ponderado.
- Implementar matchers por tipo de criterio:
  - **Texto:** similitud semántica o por palabras clave (cargo, industria, habilidades).
  - **Categórico:** coincidencia exacta o por jerarquía (modalidad, seniority).
  - **Rango numérico:** superposición de rangos salariales.
  - **Geográfico:** coincidencia de ciudad/país o aceptación de remoto.
- Implementar el filtro de curación: descartar oportunidades con score total por debajo del umbral configurado por perfil.
- Correr el scoring sobre el dataset real del POC con los 2 perfiles de fixtures creados en Subtarea 1.
- Revisar los resultados manualmente para validar que el scoring sea coherente con las expectativas.
- Ajustar pesos si los resultados no son razonables y documentar los cambios.

**Entregables:**

- Módulo `src/scoring/` con implementación del algoritmo y matchers.
- Suite de tests unitarios: mínimo un test por criterio de scoring y tests de integración sobre el dataset real.
- `docs/scoring_results.md`: resultados de scoring sobre dataset real con los 2 perfiles de ejemplo, incluyendo los top-10 matches por perfil.

**Riesgos y consideraciones:**

- La similitud semántica para matching de cargos/habilidades puede requerir un modelo de embeddings liviano; evaluar si el costo computacional es aceptable para el POC o si una comparación por keywords es suficiente.
- Los pesos iniciales (Subtarea 1) son hipótesis; es normal ajustarlos tras ver resultados reales.
- Separar claramente el cálculo del score (puro, sin efectos secundarios) del filtro de curación para facilitar el testing y la depuración.

**Criterios de aceptación:**

- [ ] El scoring produce resultados distintos y razonables para los 2 perfiles de prueba.
- [ ] El umbral de curación es configurable por perfil sin cambios en el código.
- [ ] Existe al menos un test unitario por criterio de scoring.
- [ ] Los top-10 matches de cada perfil están documentados y revisados manualmente.

---

### Subtarea 8 — Definir flujo de entrega y feedback para recomendaciones

**Objetivo:** Diseñar cómo el agente comunica las oportunidades curadas al candidato y recibe feedback para mejorar el scoring.

**Dependencias:** Subtarea 7 (formato del resultado de scoring definido). Se puede diseñar en paralelo con Subtareas 5–7 pero requiere que el esquema de oportunidad y el score estén estabilizados.

**Canal de entrega definido:** API.

**Actividades:**

- Diseñar los endpoints de la API:
  - `GET /candidates/{id}/recommendations` — devuelve oportunidades curadas paginadas, ordenadas por score descendente.
  - `POST /candidates/{id}/feedback` — recibe feedback del candidato sobre una oportunidad.
- Definir el contrato del payload de recomendación: título, empresa, ubicación, modalidad, salario estimado, fuente, URL, score de match, desglose de score por criterio, fecha de publicación.
- Definir el esquema de feedback: `{ opportunity_id, action: "applied" | "saved" | "dismissed" | "not_relevant", comment? }`.
- Diseñar el mecanismo de autenticación de la API (API key por candidato como mínimo para el POC).
- Documentar cómo el feedback alimenta el ciclo de mejora del scoring: qué señales ajustan qué pesos y con qué frecuencia se recalculan.
- Diseñar el contrato del Webhook para notificaciones push (nuevo lote de recomendaciones disponible).

**Entregables:**

- Especificación OpenAPI (`docs/api/openapi.yaml`) con todos los endpoints, schemas y ejemplos.
- Diagrama del ciclo de feedback (`docs/feedback_cycle.png` o diagrama ASCII) mostrando el flujo desde la acción del usuario hasta el ajuste del scoring.
- Documento de decisión sobre autenticación y versionado de la API.

**Riesgos y consideraciones:**

- El desglose de score por criterio en el payload es muy valioso para la experiencia del candidato pero puede exponer la lógica interna del sistema; decidir si se incluye en el POC o se reserva para una versión posterior.
- El ciclo de feedback completo (señales → ajuste de pesos → rescore) es complejo; para el POC es suficiente con diseñarlo y dejar los hooks en el código aunque no esté activo.
- Versionar la API desde el inicio (`/v1/`) para evitar breaking changes cuando el contrato evolucione.

**Criterios de aceptación:**

- [ ] La especificación OpenAPI cubre todos los endpoints con ejemplos de request y response.
- [ ] El payload de recomendación incluye al menos: título, empresa, fuente, score total, desglose por criterio y enlace.
- [ ] El ciclo de feedback está diseñado y documentado, aunque no implementado en esta subtarea.
- [ ] La estrategia de autenticación está definida y documentada.

---

## 6. Decisiones Pendientes

| #   | Decisión                                     | Estado                                   | Dependencia                   |
| --- | -------------------------------------------- | ---------------------------------------- | ----------------------------- |
| D1  | Stack tecnológico                            | ✅ Definido: Python + TypeScript         | —                             |
| D2  | Framework de orquestación                    | ✅ Definido: Hermes                      | Resultado de Subtarea 3       |
| D3  | Canal de entrega de recomendaciones          | ✅ Definido: API / Webhook               | —                             |
| D4  | Tecnología de almacenamiento (DB / store)    | ⏳ Por definir                           | Antes de Subtarea 5           |
| D5  | Portales públicos a scrapear                 | ✅ Definido: Indeed, Glassdoor, InfoJobs | —                             |
| D6  | Acceso a LinkedIn API (aprobación de cuenta) | ❌ No iniciado — **Urgente**             | Gestionar antes de Subtarea 4 |

---

## 7. Criterios de Aceptación

Para considerar el proyecto completado en su fase inicial (POC):

- [ ] El agente ingesta oportunidades de al menos **2 fuentes distintas**.
- [ ] El sistema gestiona **múltiples perfiles de candidato** de forma independiente.
- [ ] Cada oportunidad tiene un **score de match** calculado por perfil.
- [ ] Las oportunidades curadas son **entregadas al candidato** vía API.
- [ ] Existe un mecanismo de **feedback** documentado (aunque sea básico).
- [ ] El código del POC está **documentado y es reproducible**.
- [ ] El framework de orquestación (**Hermes**) está integrado y justificado.

---

_Última actualización: 2026-05-20_
