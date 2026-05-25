import { useState } from 'react'
import { searchJobs } from './api/jobs'
import JobCard from './components/JobCard'
import Pagination from './components/Pagination'
import SearchForm from './components/SearchForm'
import type { Job, SearchParams } from './types/job'

interface SearchState {
  params: SearchParams
  jobs: Job[]
  total: number
  pages: number
  error: string | null
}

export default function App() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SearchState | null>(null)

  async function handleSearch(params: SearchParams) {
    setLoading(true)
    try {
      const data = await searchJobs(params)
      setResult({ params, jobs: data.jobs, total: data.total, pages: data.pages, error: null })
    } catch (err) {
      setResult({
        params,
        jobs: [],
        total: 0,
        pages: 0,
        error: err instanceof Error ? err.message : 'Error desconocido',
      })
    } finally {
      setLoading(false)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  function handlePageChange(page: number) {
    if (!result) return
    handleSearch({ ...result.params, page })
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-gradient-to-r from-brand-900 to-brand-700 text-white py-10 px-4">
        <div className="max-w-5xl mx-auto">
          <h1 className="text-3xl font-bold tracking-tight mb-1">JobSearcher</h1>
          <p className="text-brand-100 text-sm">
            Encontrá ofertas de trabajo por rubro y país en un solo lugar
          </p>
        </div>
      </header>

      {/* Search */}
      <div className="max-w-5xl mx-auto px-4 -mt-6">
        <SearchForm onSearch={handleSearch} loading={loading} />
      </div>

      {/* Results */}
      <main className="max-w-5xl mx-auto px-4 py-8">
        {loading && (
          <div className="flex justify-center items-center py-24">
            <div className="w-10 h-10 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin" />
          </div>
        )}

        {!loading && result?.error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-5 py-4 text-sm">
            {result.error}
          </div>
        )}

        {!loading && result && !result.error && (
          <>
            <p className="text-sm text-slate-500 mb-5">
              {result.total > 0
                ? `${result.total.toLocaleString('es')} resultado${result.total !== 1 ? 's' : ''} encontrado${result.total !== 1 ? 's' : ''}`
                : 'No se encontraron resultados para tu búsqueda.'}
            </p>

            <div className="grid gap-4 sm:grid-cols-2">
              {result.jobs.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>

            <Pagination
              page={result.params.page}
              pages={result.pages}
              onPageChange={handlePageChange}
            />
          </>
        )}

        {!loading && !result && (
          <div className="text-center py-24 text-slate-400">
            <svg
              className="w-16 h-16 mx-auto mb-4 opacity-30"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <p className="text-lg font-medium">Seleccioná un país y buscá empleos</p>
            <p className="text-sm mt-1">Podés filtrar por rubro o usar palabras clave</p>
          </div>
        )}
      </main>
    </div>
  )
}
