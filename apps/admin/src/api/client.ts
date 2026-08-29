import { captureFrontendEvent } from '../frontend-telemetry'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

type ApiResponse<T> = { data: T; meta: Record<string, unknown> }
type ApiErrorPayload = {
  error?: {
    code?: string
    message?: string
    details?: Record<string, unknown>
  }
}

export class ApiError extends Error {
  status: number
  code?: string
  details?: Record<string, unknown>

  constructor(
    message: string,
    status: number,
    code?: string,
    details?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function headers(token?: string): HeadersInit {
  return {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

async function parseResponse<T>(response: Response, path: string, method: string): Promise<T> {
  const payload = (await response.json().catch(() => ({}))) as ApiResponse<T> & ApiErrorPayload
  if (!response.ok) {
    const error = new ApiError(
      payload.error?.message || `Erro HTTP ${response.status}`,
      response.status,
      payload.error?.code,
      payload.error?.details,
    )
    captureFrontendEvent('ERROR', 'api_request_failed', error.message, {
      method,
      path,
      status: response.status,
      code: error.code,
      details: error.details,
    })
    if (error.code === 'AUTH_SECOND_FACTOR_REQUIRED') {
      window.dispatchEvent(new CustomEvent('scheduler-pro-admin-2fa-required', {
        detail: { details: error.details || {} },
      }))
    }
    throw error
  }
  return payload.data as T
}

export async function apiGet<T>(path: string, token?: string): Promise<T> {
  return parseResponse<T>(
    await fetch(`${API_BASE_URL}${path}`, { headers: headers(token) }),
    path,
    'GET',
  )
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  token?: string,
): Promise<T> {
  return parseResponse<T>(
    await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: headers(token),
      body: JSON.stringify(body),
    }),
    path,
    'POST',
  )
}

export async function apiPut<T>(
  path: string,
  body: unknown,
  token?: string,
): Promise<T> {
  return parseResponse<T>(
    await fetch(`${API_BASE_URL}${path}`, {
      method: 'PUT',
      headers: headers(token),
      body: JSON.stringify(body),
    }),
    path,
    'PUT',
  )
}

export async function apiDelete<T>(path: string, token?: string): Promise<T> {
  return parseResponse<T>(
    await fetch(`${API_BASE_URL}${path}`, {
      method: 'DELETE',
      headers: headers(token),
    }),
    path,
    'DELETE',
  )
}

export async function apiPostForm<T>(path: string, form: FormData, token?: string): Promise<T> {
  return parseResponse<T>(
    await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: { Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: form,
    }),
    path,
    'POST',
  )
}

export async function apiDownloadFile(path: string, filename: string, token?: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: '*/*', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload
    throw new ApiError(
      payload.error?.message || `Erro HTTP ${response.status}`,
      response.status,
      payload.error?.code,
      payload.error?.details,
    )
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  try {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    anchor.style.display = 'none'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}
