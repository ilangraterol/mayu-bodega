/**
 * Per-line surcharge picker for the till.
 *
 * The cashier mostly reuses what the catalogue already resolved, so the row
 * starts collapsed and shows only the current percentage plus where it came
 * from. Expanding it exposes the quick picks and a custom field. Choosing a
 * value that equals the inherited one is treated as "no opinion": the line goes
 * back to sending nothing, so the article is never pinned to a value that was
 * only confirmed.
 */

import { useId, useState } from 'react'

import { formatPercent } from '../../lib/money'
import { SURCHARGE_SOURCE, type SurchargeSource } from '../../types/api'

/** Mirrors `catalog.surcharge.SURCHARGE_PRESETS`, with 0 as the "no surcharge" pick. */
const SURCHARGE_CHOICES = ['0', '3', '5', '10', '15', '30'] as const

const SOURCE_LABELS: Record<string, string> = {
  [SURCHARGE_SOURCE.PRODUCT]: 'del artículo',
  [SURCHARGE_SOURCE.CATEGORY]: 'de la categoría',
  [SURCHARGE_SOURCE.STORE]: 'de la tienda',
  [SURCHARGE_SOURCE.MANUAL]: 'elegido aquí',
}

export interface SurchargePickerProps {
  /** The catalogue-resolved percentage, pre-selected and highlighted. */
  inheritedPercentage: number
  /** `PRODUCT`, `CATEGORY` or `STORE`: why that number is the default. */
  inheritedSource: SurchargeSource
  /** The cashier's choice, or `null` while the line still follows the catalogue. */
  value: number | null
  onChange: (value: number | null) => void
}

export function SurchargePicker({
  inheritedPercentage,
  inheritedSource,
  value,
  onChange,
}: SurchargePickerProps) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const id = useId()

  const effective = value ?? inheritedPercentage
  const customised = value !== null && value !== inheritedPercentage
  const sourceLabel = customised
    ? SOURCE_LABELS[SURCHARGE_SOURCE.MANUAL]
    : (SOURCE_LABELS[inheritedSource] ?? 'del catálogo')
  function choose(percentage: number) {
    // Confirming the inherited value means "leave it to the catalogue".
    onChange(percentage === inheritedPercentage ? null : percentage)
    setOpen(false)
  }

  function applyDraft() {
    const parsed = Number(draft)
    if (!draft.trim() || Number.isNaN(parsed) || parsed < 0 || parsed > 100) return
    choose(Number(parsed.toFixed(2)))
    setDraft('')
  }

  return (
    <div className="mt-1.5">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-controls={id}
        className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium active:bg-slate-100 ${
          customised
            ? 'border-amber-300 bg-amber-50 text-amber-900'
            : 'border-slate-200 bg-slate-50 text-slate-600'
        }`}
      >
        <span aria-hidden="true">+%</span>
        {formatPercent(effective)}
        <span className="font-normal text-slate-500">{sourceLabel}</span>
        <span aria-hidden="true" className="text-slate-400">
          {open ? '▴' : '▾'}
        </span>
      </button>

      {open ? (
        <div
          id={id}
          className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-2"
        >
          <div className="flex flex-wrap gap-1.5">
            {SURCHARGE_CHOICES.map((choice) => {
              const percentage = Number(choice)
              const selected = effective === percentage
              return (
                <button
                  key={choice}
                  type="button"
                  onClick={() => choose(percentage)}
                  aria-pressed={selected}
                  className={`tabular min-w-11 rounded-lg border px-2 py-1.5 text-sm font-medium active:bg-slate-200 ${
                    selected
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-300 bg-white text-slate-700'
                  }`}
                >
                  {percentage}%
                </button>
              )
            })}
          </div>

          <div className="mt-2 flex items-end gap-2">
            <div className="min-w-0 flex-1">
              <label
                htmlFor={`${id}-custom`}
                className="block text-[11px] font-medium text-slate-600"
              >
                Otro valor (0 a 100%)
              </label>
              <input
                id={`${id}-custom`}
                type="number"
                inputMode="decimal"
                min="0"
                max="100"
                step="0.01"
                value={draft}
                placeholder={formatPercent(inheritedPercentage)}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') applyDraft()
                }}
                className="tabular mt-1 w-full min-h-10 rounded-lg border border-slate-300 bg-white px-2 text-sm text-slate-900 focus:border-slate-900 focus:outline-none"
              />
            </div>
            <button
              type="button"
              onClick={applyDraft}
              disabled={!draft.trim()}
              className="min-h-10 shrink-0 rounded-lg bg-slate-900 px-3 text-sm font-medium text-white active:bg-slate-700 disabled:opacity-40"
            >
              Aplicar
            </button>
          </div>

          {value !== null && value !== inheritedPercentage ? (
            <button
              type="button"
              onClick={() => {
                onChange(null)
                setOpen(false)
              }}
              className="mt-2 text-[11px] text-slate-500 underline active:text-slate-800"
            >
              Volver al {formatPercent(inheritedPercentage)} del catálogo
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
