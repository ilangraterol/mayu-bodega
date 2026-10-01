/**
 * Media URL normalisation.
 *
 * The API answers with absolute URLs built from the request host, so through the
 * Vite proxy it returns `http://127.0.0.1:8000/media/...`. On a phone that host
 * is the phone itself, so every product photo would fail to load. The frontend
 * and the API share an origin (Vite proxies `/api` and `/media`), so keeping only
 * the path always resolves against whatever host the app was opened with.
 *
 * Lives outside the component because `react-refresh` only works when a file
 * exports components alone.
 */

export function toSameOrigin(src: string): string {
  if (!src.startsWith('http://') && !src.startsWith('https://')) return src
  try {
    return new URL(src).pathname
  } catch {
    return src
  }
}
