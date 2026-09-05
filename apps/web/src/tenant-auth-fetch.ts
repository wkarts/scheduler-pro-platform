type RefreshEnvelope = {
  data?: { access_token?: string; refresh_token?: string }
}
type RefreshResult = { state: 'ok'; token: string } | { state: 'invalid' } | { state: 'temporary' }

let installed = false
let refreshPromise: Promise<RefreshResult> | null = null
let refreshRetryAt = 0
const inflightReads = new Map<string, Promise<Response>>()

function isSchedulerApi(url: URL): boolean {
  return url.origin === window.location.origin && url.pathname.startsWith('/api/v1/')
}
function isAuthBootstrap(url: URL): boolean {
  return [
    '/api/v1/auth/login', '/api/v1/auth/refresh',
    '/api/v1/auth/password-reset/request', '/api/v1/auth/password-reset/confirm',
  ].includes(url.pathname)
}
function isRealtimeOrStreaming(url: URL): boolean {
  return url.pathname.startsWith('/api/v1/realtime/') || url.pathname.includes('/stream')
}
function currentAccessToken(): string { return localStorage.getItem('scheduler_pro_access_token') || '' }
function currentRefreshToken(): string { return localStorage.getItem('scheduler_pro_refresh_token') || '' }
function clearTenantSession(): void {
  localStorage.removeItem('scheduler_pro_access_token')
  localStorage.removeItem('scheduler_pro_refresh_token')
  localStorage.removeItem('scheduler_pro_realtime_sequence')
  inflightReads.clear()
}
function storeTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem('scheduler_pro_access_token', accessToken)
  localStorage.setItem('scheduler_pro_refresh_token', refreshToken)
}
function temporarilyUnavailable(): Response {
  window.dispatchEvent(new CustomEvent('scheduler-pro-service-unavailable'))
  return new Response(JSON.stringify({ error: {
    code: 'SERVICE_TEMPORARILY_UNAVAILABLE',
    message: 'Não foi possível validar a sessão agora. Tente novamente em instantes.',
    details: { retryable: true },
  } }), { status: 503, headers: {
    'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Retry-After': '5',
  } })
}
async function refreshAccessToken(nativeFetch: typeof window.fetch, rejectedToken: string): Promise<RefreshResult> {
  if (refreshPromise) return refreshPromise
  const perform = async (): Promise<RefreshResult> => {
    // A previous request or another tab may already have rotated the token.
    const current = currentAccessToken()
    if (current && current !== rejectedToken) return { state: 'ok', token: current }
    const refreshToken = currentRefreshToken()
    if (!refreshToken) return { state: 'invalid' }
    if (Date.now() < refreshRetryAt) return { state: 'temporary' }
    try {
      const response = await nativeFetch(`${window.location.origin}/api/v1/auth/refresh`, {
        method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }), cache: 'no-store',
        signal: AbortSignal.timeout(15000),
      })
      const payload = await response.json().catch(() => ({})) as RefreshEnvelope
      // Never destroy a newer login completed while this request was in flight.
      if (currentRefreshToken() !== refreshToken) {
        const latest = currentAccessToken()
        return latest ? { state: 'ok', token: latest } : { state: 'invalid' }
      }
      if (response.status === 401) {
        clearTenantSession()
        return { state: 'invalid' }
      }
      const accessToken = payload.data?.access_token || ''
      const rotatedRefresh = payload.data?.refresh_token || ''
      if (!response.ok || !accessToken || !rotatedRefresh) {
        refreshRetryAt = Date.now() + 5000
        return { state: 'temporary' }
      }
      storeTokens(accessToken, rotatedRefresh)
      refreshRetryAt = 0
      inflightReads.clear()
      window.dispatchEvent(new CustomEvent('scheduler-pro-session-refreshed'))
      return { state: 'ok', token: accessToken }
    } catch {
      refreshRetryAt = Date.now() + 5000
      return { state: 'temporary' }
    }
  }
  // Web Locks serialize refresh rotation across tabs of the same origin.
  // The in-page promise remains the fallback where Web Locks is unavailable.
  refreshPromise = (typeof navigator !== 'undefined' && navigator.locks
    ? navigator.locks.request('scheduler-pro-tenant-refresh', perform)
    : perform()).finally(() => { refreshPromise = null })
  return refreshPromise
}
function requestUrl(input: RequestInfo | URL): URL {
  return new URL(input instanceof Request ? input.url : String(input), window.location.origin)
}
function requestMethod(input: RequestInfo | URL, init?: RequestInit): string {
  return String(init?.method || (input instanceof Request ? input.method : 'GET')).toUpperCase()
}
function withCurrentAuthorization(
  input: RequestInfo | URL, init: RequestInit | undefined, token: string,
): [RequestInfo | URL, RequestInit | undefined] {
  const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : {}))
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const options: RequestInit = { ...init, headers, cache: 'no-store' }
  // Clone before sending: a 401 must not consume the only copy of a POST body.
  return input instanceof Request ? [new Request(input.clone(), options), undefined] : [input, options]
}
async function authorizedFetch(
  nativeFetch: typeof window.fetch, input: RequestInfo | URL, init?: RequestInit,
): Promise<Response> {
  const accessToken = currentAccessToken()
  const [authorizedInput, authorizedInit] = withCurrentAuthorization(input, init, accessToken)
  let response = await nativeFetch(authorizedInput, authorizedInit)
  if (response.status !== 401 || !currentRefreshToken()) return response
  const renewed = await refreshAccessToken(nativeFetch, accessToken)
  if (renewed.state === 'temporary') return temporarilyUnavailable()
  if (renewed.state === 'invalid') {
    window.dispatchEvent(new CustomEvent('scheduler-pro-realtime-unauthorized', {
      detail: { status: 401, reason: 'session_invalid' },
    }))
    return response
  }
  const [retryInput, retryInit] = withCurrentAuthorization(input, init, renewed.token)
  // Retry once ONLY after authentication rejection. Never replay 5xx writes.
  response = await nativeFetch(retryInput, retryInit)
  return response
}
export function installTenantAuthFetch(): void {
  if (installed) return
  installed = true
  const nativeFetch = window.fetch.bind(window)
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = requestUrl(input)
    if (!isSchedulerApi(url) || isAuthBootstrap(url)) return nativeFetch(input, init)
    const method = requestMethod(input, init)
    const canShareRead = method === 'GET' && !init?.signal && !(input instanceof Request) && !isRealtimeOrStreaming(url)
    if (!canShareRead) return authorizedFetch(nativeFetch, input, init)
    const key = `${currentAccessToken()}|${url.href}|${new Headers(init?.headers).get('Accept') || ''}`
    let pending = inflightReads.get(key)
    if (!pending) {
      pending = authorizedFetch(nativeFetch, input, init)
      inflightReads.set(key, pending)
      void pending.finally(() => {
        if (inflightReads.get(key) === pending) inflightReads.delete(key)
      }).catch(() => undefined)
    }
    return (await pending).clone()
  }
}
