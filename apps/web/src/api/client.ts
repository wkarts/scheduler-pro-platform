const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || `${window.location.origin}/api/v1`

type ApiResponse<T> = { data: T; meta: Record<string, unknown> }

export async function apiGet<T = unknown>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new Error(`API error ${response.status}`)
  const payload = (await response.json()) as ApiResponse<T>
  return payload.data
}
