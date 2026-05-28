import { useState } from 'react'
import JobsTab from './JobsTab'
import RecommendationsTab from './RecommendationsTab'
import './App.css'

export default function App() {
  const [tab, setTab] = useState('jobs')

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <span className="logo">JobSearcher</span>
          <nav className="tabs">
            <button
              className={`tab-btn ${tab === 'jobs' ? 'active' : ''}`}
              onClick={() => setTab('jobs')}
            >
              Ofertas
            </button>
            <button
              className={`tab-btn ${tab === 'recs' ? 'active' : ''}`}
              onClick={() => setTab('recs')}
            >
              Recomendaciones
            </button>
          </nav>
        </div>
      </header>
      <main className="main">
        {tab === 'jobs' ? <JobsTab /> : <RecommendationsTab />}
      </main>
    </div>
  )
}
