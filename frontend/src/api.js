const BASE = '/api'

export async function fetchJobs(filters = {}) {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== '') params.set(k, v)
  }
  const res = await fetch(`${BASE}/jobs?${params}`)
  if (!res.ok) throw new Error('Error al cargar ofertas')
  return res.json()
}

export async function fetchJob(jobId) {
  const res = await fetch(`${BASE}/jobs/${jobId}`)
  if (!res.ok) throw new Error('Error al cargar oferta')
  return res.json()
}

export async function fetchProfiles() {
  const res = await fetch(`${BASE}/profiles`)
  if (!res.ok) throw new Error('Error al cargar perfiles')
  return res.json()
}

export async function createProfile(profileData) {
  const res = await fetch(`${BASE}/profiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profileData),
  })
  if (!res.ok) throw new Error('Error al crear perfil')
  return res.json()
}

export async function fetchRecommendations(profileId) {
  const res = await fetch(`${BASE}/recommendations/${profileId}`)
  if (!res.ok) throw new Error('Error al cargar recomendaciones')
  return res.json()
}

export async function postFeedback(recId, status, note = '') {
  const res = await fetch(`${BASE}/feedback/${recId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, note }),
  })
  if (!res.ok) throw new Error('Error al guardar feedback')
  return res.json()
}
