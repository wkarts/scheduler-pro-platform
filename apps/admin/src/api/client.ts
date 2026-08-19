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
