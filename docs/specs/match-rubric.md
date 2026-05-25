# Rúbrica de Match: Oferta ↔ Perfil del Estudiante

## Lógica de Evaluación

La evaluación de una oferta tiene dos fases:

```
Fase 1: Hard Filters  →  ¿Pasa o no pasa? (binario)
Fase 2: Score         →  ¿Qué tan buena es? (0–100 puntos)
```

Una oferta que falla en Fase 1 **no se muestra**, sin importar el score.

---

## Fase 1: Hard Filters (eliminatorios)

| Criterio | Condición de eliminación |
|----------|--------------------------|
| Salario mínimo | `offer.salary_max < profile.restrictions.min_salary` |
| Modalidad | `offer.modality` no está en `profile.modality` Y `profile.restrictions.excluded_modalities` lo incluye |
| Ubicación excluida | `offer.location` está en `profile.restrictions.excluded_locations` |
| Visa requerida | `profile.restrictions.requires_visa_sponsorship = true` Y `offer.visa_sponsorship = false` |
| Viaje excesivo | `offer.travel_percent > profile.restrictions.max_travel_percent` (cuando `max_travel_percent` está definido) |

---

## Fase 2: Score de Compatibilidad (0–100)

### Criterios y pesos base

| Criterio | Peso | Cómo se calcula |
|----------|------|-----------------|
| Stack match | 35 pts | `(tecnologías en común / tecnologías del JD) × 35` |
| Seniority match | 20 pts | 20 si es junior/sin experiencia requerida; 10 si pide 1-2 años; 0 si pide 3+ |
| Idioma | 15 pts | 15 si cumple el requisito; 7 si supera lo requerido; 0 si no cumple |
| Sector preferido | 15 pts | 15 si coincide con `preferences.sectors`; 0 si no |
| Tamaño empresa | 10 pts | 10 si coincide con `preferences.company_size`; 0 si no |
| Título del rol | 5 pts | 5 si coincide con `preferences.roles` |

**Total base: 100 pts**

### Penalizaciones (no eliminatorias)

| Condición | Penalización |
|-----------|-------------|
| Sector en `avoid_sectors` | -20 pts |
| Salario por debajo del rango esperado pero sobre el mínimo | -10 pts |
| Requiere tecnología ausente en el stack del estudiante (crítica) | -15 pts |

### Ajuste por `growth_priority`

El campo `preferences.growth_priority` redistribuye los pesos:

| Prioridad | Ajuste |
|-----------|--------|
| `learning` | Stack match +5, Seniority -5 (valora aprender más que encajar perfecto) |
| `salary` | Criterio de salary +10 bonus si oferta supera `expected_salary.max` |
| `stability` | Tamaño empresa: enterprise/mid-size suman +10 extra |
| `impact` | Sector preferido +10 si el sector es ONG/govtech/social impact |

---

## Clasificación del Score Final

| Rango | Etiqueta | Acción sugerida |
|-------|----------|-----------------|
| 80–100 | Excelente match | Aplicar de inmediato |
| 60–79 | Buen match | Aplicar con adaptaciones menores al CV |
| 40–59 | Match parcial | Revisar gaps antes de aplicar |
| 0–39 | Match bajo | No se muestra (o se muestra como "fuera de rango") |

---

## Ejemplo de Evaluación

**Estudiante:** Junior frontend (React, JS, CSS) en San José, remoto preferido, salario mínimo ₡600.000 CRC/mes.

**Oferta:** Frontend Developer en startup, React + TypeScript, remoto, ₡750.000 CRC, en San José.

| Criterio | Puntos |
|----------|--------|
| Stack match: React ✓, JS ✓, TypeScript (no tiene) → 2/3 tecnologías clave | 23 |
| Seniority: "Junior / 0-1 año" | 20 |
| Idioma: inglés intermedio requerido, tiene intermedio | 15 |
| Sector: tech startup (preferido) | 15 |
| Tamaño empresa: startup (preferido) | 10 |
| Título: "Frontend Developer" coincide | 5 |
| **Total** | **88** |

→ **Excelente match.** Gap identificado: TypeScript. Acción: aplicar destacando React, mencionar disposición a aprender TypeScript.
