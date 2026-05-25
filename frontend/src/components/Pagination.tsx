interface Props {
  page: number
  pages: number
  onPageChange: (page: number) => void
}

export default function Pagination({ page, pages, onPageChange }: Props) {
  if (pages <= 1) return null

  const visible: (number | '…')[] = []
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - page) <= 2) {
      visible.push(i)
    } else if (visible[visible.length - 1] !== '…') {
      visible.push('…')
    }
  }

  return (
    <nav className="flex items-center justify-center gap-1 mt-8">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page === 1}
        className="px-3 py-1.5 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        ← Anterior
      </button>
      {visible.map((item, idx) =>
        item === '…' ? (
          <span key={`ellipsis-${idx}`} className="px-2 text-slate-400 select-none">
            …
          </span>
        ) : (
          <button
            key={item}
            onClick={() => onPageChange(item)}
            className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors ${
              item === page
                ? 'bg-brand-600 text-white'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {item}
          </button>
        ),
      )}
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page === pages}
        className="px-3 py-1.5 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Siguiente →
      </button>
    </nav>
  )
}
