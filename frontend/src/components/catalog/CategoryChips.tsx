/**
 * Horizontal category chips.
 *
 * A single row that scrolls sideways on touch: on a phone the categories have
 * to stay one tap deep instead of stacking and pushing the grid off-screen.
 * The chip strip uses `role="listbox"` with `aria-selected` because each chip
 * switches the list it filters; buttons would announce as toggles instead.
 */

import type { Category } from '../../types/api'

interface CategoryChipsProps {
  categories: Category[]
  /** `null` means "all categories". */
  value: number | null
  onChange: (value: number | null) => void
  /** Label for the "no filter" chip. */
  allLabel?: string
}

export function CategoryChips({
  categories,
  value,
  onChange,
  allLabel = 'Todas',
}: CategoryChipsProps) {
  return (
    <div
      role="listbox"
      aria-label="Filtrar por categoría"
      className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1"
    >
      <button
        type="button"
        role="option"
        aria-selected={value === null}
        onClick={() => onChange(null)}
        className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium ${
          value === null
            ? 'bg-slate-900 text-white'
            : 'border border-slate-300 bg-white text-slate-600'
        }`}
      >
        {allLabel}
      </button>
      {categories.map((category) => {
        const selected = value === category.id
        return (
          <button
            key={category.id}
            type="button"
            role="option"
            aria-selected={selected}
            onClick={() => onChange(selected ? null : category.id)}
            className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium ${
              selected
                ? 'bg-slate-900 text-white'
                : 'border border-slate-300 bg-white text-slate-600'
            }`}
          >
            {category.name}
          </button>
        )
      })}
    </div>
  )
}
