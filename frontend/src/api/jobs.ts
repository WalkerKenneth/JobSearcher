import type { Category, Country, JobSearchResponse } from '../types/job'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

async function apiFetch<T>(path: string, params: Record<string, string> = {}): Promise<T> {
  const qs = new URLSearchParams(params).toString()
  const res = await fetch(`${API_BASE}${path}${qs ? `?${qs}` : ''}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Error ${res.status}`)
  }
  return res.json()
}

export function searchJobs(params: {
  country: string
  category?: string
  keyword?: string
  page?: number
}): Promise<JobSearchResponse> {
  const query: Record<string, string> = { country: params.country }
  if (params.category) query.category = params.category
  if (params.keyword) query.keyword = params.keyword
  if (params.page && params.page > 1) query.page = String(params.page)
  return apiFetch<JobSearchResponse>('/jobs', query)
}

export function getCountries(): Promise<Country[]> {
  return apiFetch<Country[]>('/countries')
}

export function getCategories(): Promise<Category[]> {
  return apiFetch<Category[]>('/categories')
}
