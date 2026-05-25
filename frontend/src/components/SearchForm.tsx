import { FormEvent, useEffect, useState } from 'react'
import { getCategories, getCountries } from '../api/jobs'
import type { Category, Country, SearchParams } from '../types/job'

interface Props {
  onSearch: (params: SearchParams) => void
  loading: boolean
}

export default function SearchForm({ onSearch, loading }: Props) {
  const [countries, setCountries] = useState<Country[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [form, setForm] = useState<Omit<SearchParams, 'page'>>({
    country: 'us',
    category: '',
    keyword: '',
  })

  useEffect(() => {
    Promise.all([getCountries(), getCategories()]).then(([c, cat]) => {
      setCountries(c)
      setCategories(cat)
    })
  }, [])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    onSearch({ ...form, page: 1 })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-2xl shadow-md p-6 flex flex-col gap-4 md:flex-row md:items-end"
    >
      <div className="flex-1 flex flex-col gap-1">
        <label className="text-sm font-medium text-slate-600">País</label>
        <select
          value={form.country}
          onChange={(e) => setForm((f) => ({ ...f, country: e.target.value }))}
          className="border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-slate-50"
          required
        >
          {countries.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1 flex flex-col gap-1">
        <label className="text-sm font-medium text-slate-600">Rubro</label>
        <select
          value={form.category}
          onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
          className="border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-slate-50"
        >
          <option value="">Todos los rubros</option>
          {categories.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-[2] flex flex-col gap-1">
        <label className="text-sm font-medium text-slate-600">Buscar</label>
        <input
          type="text"
          placeholder="Ej: React, Data Analyst, Marketing…"
          value={form.keyword}
          onChange={(e) => setForm((f) => ({ ...f, keyword: e.target.value }))}
          className="border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-slate-50"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-semibold px-6 py-2.5 rounded-lg transition-colors text-sm whitespace-nowrap"
      >
        {loading ? 'Buscando…' : 'Buscar empleos'}
      </button>
    </form>
  )
}
