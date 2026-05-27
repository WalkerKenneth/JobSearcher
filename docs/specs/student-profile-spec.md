# Spec: Perfil del Estudiante (`StudentProfile`)

## Propósito

Define el contrato de datos que describe a un estudiante de Lyfter para ser usado en:
- Persistencia en la base de datos (`profiles` table) y gestión vía `profiles.py`
- Prompts al agente de búsqueda
- Algoritmo de scoring/ranking de ofertas
- Fixtures de prueba

---

## Fuentes de Datos (Ipsum → Perfil)

| Campo del perfil | Fuente en Ipsum | Notas |
|-----------------|-----------------|-------|
| `stack` | Módulos completados + proyectos | Tecnologías demostradas, no solo declaradas |
| `seniority` | Evaluación de egreso + horas de práctica | Mapeado a `junior` / `mid` |
| `location.city` | Datos personales | Requerido para filtrar por zona |
| `location.country` | Datos personales | |
| `modality` | Preferencia declarada + historial de estudio | Remoto / Híbrido / Presencial |
| `languages` | Evaluación de inglés u otros | Con nivel: `basic` / `intermediate` / `advanced` / `native` |
| `availability` | Declarado al egreso | Fecha de inicio disponible + horas/semana |
| `expected_salary` | Declarado en perfil de egreso | En moneda local; puede ser rango |
| `restrictions` | Declarado + inferido | Hard filters (no negociables) |
| `preferences` | Declarado | Nice-to-have (mejoran el score, no eliminan) |

> **Consentimiento:** El uso de estos datos requiere aceptación explícita del estudiante al activar el agente.

---

## Esquema JSON

```json
{
  "profile_id": "string",
  "name": "string",
  "cohort": "string",
  "stack": {
    "primary": ["string"],
    "secondary": ["string"],
    "tools": ["string"]
  },
  "seniority": "junior | mid",
  "location": {
    "city": "string",
    "country": "string",
    "timezone": "string"
  },
  "modality": ["remote", "hybrid", "on-site"],
  "languages": [
    {
      "language": "string",
      "level": "basic | intermediate | advanced | native"
    }
  ],
  "availability": {
    "start_date": "YYYY-MM-DD",
    "hours_per_week": "number",
    "type": "full-time | part-time"
  },
  "expected_salary": {
    "min": "number",
    "max": "number",
    "currency": "string",
    "period": "monthly | annual"
  },
  "restrictions": {
    "min_salary": "number | null",
    "currency": "string",
    "excluded_modalities": ["string"],
    "excluded_locations": ["string"],
    "requires_visa_sponsorship": "boolean",
    "max_travel_percent": "number | null"
  },
  "preferences": {
    "company_size": ["startup", "mid-size", "enterprise"],
    "sectors": ["string"],
    "roles": ["string"],
    "avoid_sectors": ["string"],
    "growth_priority": "learning | salary | stability | impact"
  }
}
```

---

## Hard Filters vs. Nice-to-Have

### Hard Filters (`restrictions`)
Eliminan una oferta si no se cumplen. El agente **no debe** presentar ofertas que los violen.

| Campo | Descripción |
|-------|-------------|
| `min_salary` | Salario mínimo aceptable. Ofertas por debajo → descartadas |
| `excluded_modalities` | Si el estudiante solo acepta remoto, las ofertas presenciales se descartan |
| `excluded_locations` | Ciudades/países donde no puede o no quiere trabajar |
| `requires_visa_sponsorship` | Si necesita visa y la empresa no la ofrece → descartada |
| `max_travel_percent` | Si no puede viajar, roles con >N% de viaje → descartados |

### Nice-to-Have (`preferences`)
No eliminan una oferta, pero suman o restan puntos en el score de compatibilidad.

| Campo | Impacto en score |
|-------|-----------------|
| `company_size` | +10 pts si coincide con preferencia |
| `sectors` | +15 pts por sector preferido |
| `roles` | +20 pts si el título del rol coincide |
| `avoid_sectors` | -30 pts (penalización, no eliminación) |
| `growth_priority` | Ajusta el peso de los criterios de ranking |

---

## Input / Output del Agente

### Input
Un objeto `StudentProfile` completo (ver esquema arriba).

### Output esperado
Una lista rankeada de oportunidades, donde cada ítem incluye:
```json
{
  "job_id": "string",
  "title": "string",
  "company": "string",
  "match_score": "0-100",
  "hard_filters_passed": "boolean",
  "match_reasons": ["string"],
  "gaps": ["string"],
  "action": "string"
}
```

---

---

## Persistencia en Base de Datos

Los perfiles se almacenan en la tabla `profiles` de `data/jobs.db` (misma base de datos que las ofertas). Las estructuras anidadas (`stack`, `location`, `languages`, etc.) se serializan como JSON text, consistente con el resto del esquema.

### Gestión de perfiles (`profiles.py`)

```bash
# Importar desde JSON (primera carga o actualización)
python3 profiles.py import fixtures/profiles/junior_frontend.json

# Listar todos los perfiles
python3 profiles.py list

# Ver detalle completo
python3 profiles.py show lyfter-001

# Eliminar
python3 profiles.py delete lyfter-001
```

### Repository API (`app/profiles/repository.py`)

| Función | Descripción |
|---------|-------------|
| `upsert_profile(profile)` | Inserta o actualiza un perfil; devuelve `'inserted'` / `'updated'` |
| `load_profile(profile_id)` | Retorna `StudentProfile` o `None` si no existe |
| `list_profiles()` | Lista todos los perfiles ordenados por nombre |
| `delete_profile(profile_id)` | Elimina el perfil; devuelve `True` si existía |

### Uso desde otros CLIs

`ingest.py` y `recommend.py` aceptan el perfil desde la base de datos con `--profile-id`:

```bash
python3 ingest.py --profile-id lyfter-001
python3 recommend.py --profile-id lyfter-001
```

La carga desde archivo JSON sigue funcionando para compatibilidad y flujos de prueba.

---

## Criterios de Empleabilidad Relevantes

Alineados con el equipo de Lyfter, los criterios priorizados son:

1. **Stack match** — Al menos 60% de las tecnologías del job description en el perfil del estudiante
2. **Seniority match** — El rol es explícitamente junior o no requiere más de 2 años de experiencia
3. **Modalidad compatible** — Respeta los hard filters de modalidad
4. **Salary range** — La oferta supera el `min_salary` del estudiante
5. **Idioma suficiente** — Si el rol requiere inglés avanzado, el estudiante lo tiene
