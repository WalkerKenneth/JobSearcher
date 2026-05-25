import { useState } from 'react'
import type { Job } from '../types/job'

interface Props {
  job: Job
}

function formatSalary(min?: number, max?: number): string | null {
  if (!min && !max) return null
  const fmt = (n: number) =>
    new Intl.NumberFormat('es', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)
  if (min && max) return `${fmt(min)} – ${fmt(max)}`
  if (min) return `Desde ${fmt(min)}`
  if (max) return `Hasta ${fmt(max)}`
  return null
}

function formatDate(iso: string): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })
}

const DESCRIPTION_LIMIT = 180

export default function JobCard({ job }: Props) {
  const [expanded, setExpanded] = useState(false)
  const salary = formatSalary(job.salary_min, job.salary_max)
  const isLong = job.description.length > DESCRIPTION_LIMIT
  const description =
    !isLong || expanded ? job.description : job.description.slice(0, DESCRIPTION_LIMIT) + '…'

  return (
    <article className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5 flex flex-col gap-3 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-slate-900 text-base leading-snug line-clamp-2">
            {job.title}
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">{job.company}</p>
        </div>
        {salary && (
          <span className="shrink-0 text-xs font-semibold text-brand-700 bg-brand-50 border border-brand-100 px-2.5 py-1 rounded-full">
            {salary}
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <span className="flex items-center gap-1 text-slate-500">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          {job.location || 'No especificada'}
        </span>
        {job.category && (
          <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">{job.category}</span>
        )}
        {job.created && (
          <span className="text-slate-400 ml-auto">{formatDate(job.created)}</span>
        )}
      </div>

      <p className="text-sm text-slate-600 leading-relaxed">
        {description}
        {isLong && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="ml-1 text-brand-600 hover:underline text-xs font-medium"
          >
            {expanded ? 'Ver menos' : 'Ver más'}
          </button>
        )}
      </p>

      <a
        href={job.url}
        target="_blank"
        rel="noopener noreferrer"
        className="self-start mt-auto text-sm font-medium text-brand-600 hover:text-brand-800 border border-brand-200 hover:border-brand-400 px-4 py-1.5 rounded-lg transition-colors"
      >
        Ver oferta →
      </a>
    </article>
  )
}
