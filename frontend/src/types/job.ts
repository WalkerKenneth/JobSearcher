export interface Job {
  id: string
  title: string
  company: string
  location: string
  description: string
  url: string
  salary_min?: number
  salary_max?: number
  created: string
  category: string
}

export interface JobSearchResponse {
  jobs: Job[]
  total: number
  page: number
  pages: number
}

export interface Country {
  code: string
  name: string
}

export interface Category {
  code: string
  name: string
}

export interface SearchParams {
  country: string
  category: string
  keyword: string
  page: number
}
