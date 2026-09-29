/** Shared mutation primitive: pending/error state plus cache invalidation. */

import { useCallback, useState } from 'react'

import { ApiError } from '../lib/apiClient'
import { invalidate } from '../lib/queryCache'

export interface MutationResult<TInput, TOutput> {
  mutate: (input: TInput) => Promise<TOutput>
  isPending: boolean
  error: ApiError | null
  reset: () => void
}

export interface MutationOptions {
  /** Cache key prefixes to bust on success. */
  invalidates?: string[]
  onSuccess?: (data: unknown) => void
  onError?: (error: ApiError) => void
}

export function useMutation<TInput, TOutput>(
  action: (input: TInput) => Promise<TOutput>,
  options: MutationOptions = {},
): MutationResult<TInput, TOutput> {
  const [isPending, setIsPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const { invalidates, onSuccess, onError } = options

  const reset = useCallback(() => setError(null), [])

  const mutate = useCallback(
    async (input: TInput): Promise<TOutput> => {
      setIsPending(true)
      setError(null)
      try {
        const data = await action(input)
        if (invalidates?.length) invalidate(invalidates)
        onSuccess?.(data)
        return data
      } catch (caught) {
        const apiError =
          caught instanceof ApiError ? caught : new ApiError(0, 'Error inesperado.', {})
        setError(apiError)
        onError?.(apiError)
        throw apiError
      } finally {
        setIsPending(false)
      }
    },
    // `action` must be a stable reference from the caller.
    [action, invalidates, onSuccess, onError],
  )

  return { mutate, isPending, error, reset }
}
