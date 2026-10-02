/** Form primitives: text inputs, selects, toggles and labels. */

import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import { useId } from 'react'

const FIELD_BASE =
  'w-full min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 ' +
  'placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-1 focus:ring-slate-900 ' +
  'disabled:bg-slate-100 disabled:text-slate-500'

interface FieldProps {
  label: string
  /** Rendered in the label slot instead of the text, e.g. the animated
      search icon on the point of sale. */
  icon?: ReactNode
  hint?: string
  error?: string
  required?: boolean
  children: (id: string) => ReactNode
}

/** Wraps a control with its label, hint and error message. */
export function Field({ label, icon, hint, error, required, children }: FieldProps) {
  const id = useId()
  return (
    <div className="space-y-1.5">
      {label || icon ? (
        <label
          htmlFor={id}
          className={`block text-sm font-medium text-slate-700 ${
            icon && !label ? 'flex justify-center' : ''
          }`}
        >
          {icon ?? label}
          {required ? <span className="ml-0.5 text-red-600">*</span> : null}
        </label>
      ) : null}
      {children(id)}
      {error ? (
        <p className="text-xs text-red-600" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="text-xs text-slate-500">{hint}</p>
      ) : null}
    </div>
  )
}

interface TextInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  label: string
  icon?: ReactNode
  hint?: string
  error?: string
}

export function TextInput({
  label,
  icon,
  hint,
  error,
  required,
  className = '',
  ...rest
}: TextInputProps) {
  return (
    <Field label={label} icon={icon} hint={hint} error={error} required={required}>
      {(id) => (
        <input
          {...rest}
          id={id}
          className={`${FIELD_BASE} ${error ? 'border-red-400' : ''} ${className}`}
        />
      )}
    </Field>
  )
}

/** Numeric input that keeps a numeric keypad on mobile but stays typeable. */
export function NumberInput({
  label,
  hint,
  error,
  required,
  className = '',
  ...rest
}: TextInputProps) {
  return (
    <Field label={label} hint={hint} error={error} required={required}>
      {(id) => (
        <input
          {...rest}
          id={id}
          type="number"
          inputMode="decimal"
          step="0.01"
          min="0"
          className={`${FIELD_BASE} tabular ${error ? 'border-red-400' : ''} ${className}`}
        />
      )}
    </Field>
  )
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id'> {
  label: string
  hint?: string
  error?: string
  options: { value: string; label: string }[]
  placeholder?: string
}

export function Select({
  label,
  hint,
  error,
  required,
  options,
  placeholder,
  className = '',
  ...rest
}: SelectProps) {
  return (
    <Field label={label} hint={hint} error={error} required={required}>
      {(id) => (
        <select
          {...rest}
          id={id}
          className={`${FIELD_BASE} appearance-none pr-8 ${error ? 'border-red-400' : ''} ${className}`}
        >
          {placeholder ? <option value="">{placeholder}</option> : null}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  )
}

interface ToggleProps {
  label: string
  description?: string
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}

export function Toggle({ label, description, checked, onChange, disabled }: ToggleProps) {
  return (
    <label
      className={`flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-white p-3 ${
        disabled ? 'opacity-60' : ''
      }`}
    >
      <span className="flex-1">
        <span className="block text-sm font-medium text-slate-800">{label}</span>
        {description ? (
          <span className="mt-0.5 block text-xs text-slate-500">{description}</span>
        ) : null}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors ${
          checked ? 'bg-emerald-600' : 'bg-slate-300'
        }`}
      >
        <span
          className={`absolute left-0.5 top-0.5 size-5 rounded-full bg-white shadow transition-transform ${
            checked ? 'translate-x-5' : 'translate-x-0'
          }`}
        />
      </button>
    </label>
  )
}
