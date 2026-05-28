import { useState, useEffect } from 'react'
import { fetchProfiles, fetchRecommendations, postFeedback } from './api'

function ScoreBar({ score }) {
  const color = score >= 70 ? '#16a34a' : score >= 50 ? '#d97706' : '#dc2626'
  return (
    <div className="score-bar-wrap">
      <div className="score-bar-bg">
        <div
          className="score-bar-fill"
          style={{ width: `${score}%`, background: color }}
        />
      </div>
      <span className="score-label" style={{ color }}>{score}</span>
    </div>
  )
}

const FEEDBACK_OPTIONS = [
  { value: 'seen', label: 'Visto', variant: 'secondary' },
  { value: 'applied', label: 'Aplicado', variant: 'success' },
  { value: 'discarded', label: 'Descartado', variant: 'danger' },
  { value: 'needs_coach', label: 'Necesita Coach', variant: 'warning' },
]

function RecCard({ rec, onFeedback }) {
  const [status, setStatus] = useState(rec.status)
  const [busy, setBusy] = useState(false)

  const handleFeedback = async (newStatus) => {
    if (busy || status === newStatus) return
    setBusy(true)
    try {
      await onFeedback(rec.rec_id, newStatus)
      setStatus(newStatus)
    } catch (e) {
      console.error(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`rec-card ${status === 'discarded' ? 'rec-discarded' : ''}`}>
      <div className="rec-card-header">
        <div className="rec-info">
          <h3 className="rec-title">{rec.title ?? rec.job_id}</h3>
          <p className="rec-company">
            {rec.company}
            {rec.is_remote ? ' · Remoto' : ''}
          </p>
          {rec.location && <p className="rec-location">📍 {rec.location}</p>}
        </div>
        <div className="rec-score-col">
          <ScoreBar score={rec.match_score} />
          <span className="rec-action-badge">{rec.next_action}</span>
        </div>
      </div>

      {rec.match_reasons?.length > 0 && (
        <div className="reasons">
          {rec.match_reasons.map((r, i) => (
            <span key={i} className="reason-tag">✓ {r}</span>
          ))}
        </div>
      )}

      {rec.gaps?.length > 0 && (
        <div className="gaps">
          {rec.gaps.map((g, i) => (
            <span key={i} className="gap-tag">✗ {g}</span>
          ))}
        </div>
      )}

      <div className="rec-card-footer">
        <div className="feedback-btns">
          {FEEDBACK_OPTIONS.map(opt => (
            <button
              key={opt.value}
              className={`btn btn-sm btn-${opt.variant} ${status === opt.value ? 'active' : ''}`}
              disabled={busy || status === opt.value}
              onClick={() => handleFeedback(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {rec.apply_url && (
          <a
            href={rec.apply_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary btn-sm"
          >
            Aplicar →
          </a>
        )}
      </div>
    </div>
  )
}

export default function RecommendationsTab() {
  const [profiles, setProfiles] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [recs, setRecs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchProfiles()
      .then(data => {
        setProfiles(data)
        if (data.length > 0) setSelectedId(data[0].profile_id)
      })
      .catch(console.error)
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setLoading(true)
    setError(null)
    fetchRecommendations(selectedId)
      .then(setRecs)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedId])

  const handleFeedback = async (recId, status) => {
    await postFeedback(recId, status)
    setRecs(prev => prev.map(r => r.rec_id === recId ? { ...r, status } : r))
  }

  return (
    <div>
      <div className="filter-bar">
        {profiles.length === 0 ? (
          <p className="hint">
            Sin perfiles en BD — importa uno:&nbsp;
            <code>python profiles.py import &lt;archivo.json&gt;</code>
          </p>
        ) : (
          <select
            className="filter-select filter-select-wide"
            value={selectedId}
            onChange={e => setSelectedId(e.target.value)}
          >
            {profiles.map(p => (
              <option key={p.profile_id} value={p.profile_id}>
                {p.name} — {p.cohort} ({p.seniority})
              </option>
            ))}
          </select>
        )}
      </div>

      {loading && <div className="loading">Cargando recomendaciones…</div>}
      {error && <div className="error">{error}</div>}

      {!loading && !error && recs.length === 0 && selectedId && (
        <div className="empty">
          Sin recomendaciones para este perfil.
          <br />
          Ejecuta: <code>python recommend.py --profile-id {selectedId}</code>
        </div>
      )}

      {!loading && !error && recs.length > 0 && (
        <>
          <p className="results-count">{recs.length} recomendación{recs.length !== 1 ? 'es' : ''}</p>
          <div className="recs-list">
            {recs.map(rec => (
              <RecCard key={rec.rec_id} rec={rec} onFeedback={handleFeedback} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
