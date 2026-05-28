import { useState, useEffect } from 'react'
import { fetchJobs, fetchJob } from './api'

function Badge({ variant, children }) {
  return <span className={`badge badge-${variant}`}>{children}</span>
}

function TagList({ tags, max = 6 }) {
  if (!tags?.length) return null
  return (
    <div className="tag-list">
      {tags.slice(0, max).map(t => (
        <span key={t} className="tag">{t}</span>
      ))}
      {tags.length > max && <span className="tag tag-more">+{tags.length - max}</span>}
    </div>
  )
}

function JobCard({ job, onDetail }) {
  const locationParts = [job.location_city, job.location_country].filter(Boolean)
  return (
    <div className="job-card">
      <div className="job-card-header">
        <div className="job-card-info">
          <h3 className="job-title">{job.job_title}</h3>
          <p className="job-company">{job.company_name}</p>
        </div>
        <div className="job-badges">
          <Badge variant={job.status}>{job.status}</Badge>
          {job.is_remote && <Badge variant="remote">Remoto</Badge>}
          <Badge variant="seniority">{job.seniority_signal}</Badge>
        </div>
      </div>
      {locationParts.length > 0 && (
        <p className="job-location">📍 {locationParts.join(', ')}</p>
      )}
      <TagList tags={job.stack_keywords} />
      <div className="job-card-footer">
        <span className="job-source">{job.source}</span>
        <button className="btn btn-secondary btn-sm" onClick={() => onDetail(job.job_id)}>
          Ver detalle
        </button>
      </div>
    </div>
  )
}

function JobModal({ jobId, onClose }) {
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!jobId) return
    setLoading(true)
    setJob(null)
    fetchJob(jobId)
      .then(setJob)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [jobId])

  if (!jobId) return null

  const locationParts = job ? [job.location_city, job.location_country].filter(Boolean) : []

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Cerrar">✕</button>
        {loading && <div className="loading">Cargando...</div>}
        {!loading && !job && <p className="empty">No se encontró la oferta.</p>}
        {!loading && job && (
          <>
            <h2 className="modal-title">{job.job_title}</h2>
            <p className="modal-company">{job.company_name}</p>
            <div className="modal-meta">
              {locationParts.length > 0 && <span>📍 {locationParts.join(', ')}</span>}
              {job.is_remote && <Badge variant="remote">Remoto</Badge>}
              <Badge variant="seniority">{job.seniority_signal}</Badge>
              <Badge variant="source">{job.source}</Badge>
              <Badge variant={job.status}>{job.status}</Badge>
            </div>
            {job.salary_min != null && (
              <p className="modal-salary">
                💰 {job.salary_min.toLocaleString()} – {job.salary_max?.toLocaleString()} {job.salary_currency} / {job.salary_period}
              </p>
            )}
            {job.stack_keywords?.length > 0 && (
              <div className="modal-section">
                <h4>Stack</h4>
                <TagList tags={job.stack_keywords} max={20} />
              </div>
            )}
            {job.qualifications_raw?.length > 0 && (
              <div className="modal-section">
                <h4>Requisitos</h4>
                <ul className="qual-list">
                  {job.qualifications_raw.map((q, i) => <li key={i}>{q}</li>)}
                </ul>
              </div>
            )}
            {job.description_raw && (
              <div className="modal-section">
                <h4>Descripción</h4>
                <p className="modal-description">
                  {job.description_raw.length > 700
                    ? job.description_raw.slice(0, 700) + '…'
                    : job.description_raw}
                </p>
              </div>
            )}
            <div className="modal-footer">
              <a
                href={job.apply_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-primary"
              >
                Aplicar →
              </a>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default function JobsTab() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    q: '', status: '', source: '', seniority: '', is_remote: '',
  })
  const [selectedJobId, setSelectedJobId] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchJobs(filters)
      .then(setJobs)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [filters])

  const set = (key, value) => setFilters(f => ({ ...f, [key]: value }))

  return (
    <div>
      <div className="filter-bar">
        <input
          className="filter-input"
          type="text"
          placeholder="Buscar por título o empresa…"
          value={filters.q}
          onChange={e => set('q', e.target.value)}
        />
        <select className="filter-select" value={filters.status} onChange={e => set('status', e.target.value)}>
          <option value="">Estado: todos</option>
          <option value="active">Activo</option>
          <option value="stale">Antiguo</option>
          <option value="expired">Expirado</option>
        </select>
        <select className="filter-select" value={filters.is_remote} onChange={e => set('is_remote', e.target.value)}>
          <option value="">Modalidad: todas</option>
          <option value="true">Remoto</option>
          <option value="false">Presencial</option>
        </select>
        <select className="filter-select" value={filters.seniority} onChange={e => set('seniority', e.target.value)}>
          <option value="">Seniority: todos</option>
          <option value="junior">Junior</option>
          <option value="mid">Mid</option>
          <option value="senior">Senior</option>
          <option value="unknown">Desconocido</option>
        </select>
        <select className="filter-select" value={filters.source} onChange={e => set('source', e.target.value)}>
          <option value="">Fuente: todas</option>
          <option value="jsearch">JSearch</option>
          <option value="serpapi">SerpAPI</option>
        </select>
      </div>

      {loading ? (
        <div className="loading">Cargando ofertas…</div>
      ) : (
        <>
          <p className="results-count">{jobs.length} oferta{jobs.length !== 1 ? 's' : ''}</p>
          {jobs.length === 0 ? (
            <div className="empty">No hay ofertas con los filtros aplicados.</div>
          ) : (
            <div className="jobs-grid">
              {jobs.map(job => (
                <JobCard key={job.job_id} job={job} onDetail={setSelectedJobId} />
              ))}
            </div>
          )}
        </>
      )}

      <JobModal jobId={selectedJobId} onClose={() => setSelectedJobId(null)} />
    </div>
  )
}
