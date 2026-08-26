type RefreshEnvelope = {
  data?: {
    access_token?: string
    refresh_token?: string
  }
}

let installed = false
let refreshPromise: Promise<string | null> | null = null

function isSchedulerApi(url: URL): boolean {
  return url.origin === window.location.origin && url.pathname.startsWith('/api/v1/')
}

function isAuthBootstrap(url: URL): boolean {
  return [
    '/api/v1/auth/login',
    '/api/v1/auth/refresh',
    '/api/v1/auth/password-reset/request',
    '/api/v1/auth/password-reset/confirm',
  ].some((path) => url.pathname === path)
}

function currentAccessToken(): string {
  return localStorage.getItem('scheduler_pro_access_token') || ''
}

function currentRefreshToken(): string {
  return localStorage.getItem('scheduler_pro_refresh_token') || ''
}

function clearTenantSession(): void {
  localStorage.removeItem('scheduler_pro_access_token')
  localStorage.removeItem('scheduler_pro_refresh_token')
  localStorage.removeItem('scheduler_pro_realtime_sequence')
}

async function refreshAccessToken(nativeFetch: typeof window.fetch): Promise<string | null> {
  if (refreshPromise) return refreshPromise
  const refreshToken = currentRefreshToken()
  if (!refreshToken) return null

  refreshPromise = (async () => {
    try {
      const response = await nativeFetch(`${window.location.origin}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: 'no-store',
      })
      const payload = await response.json().catch(() => ({})) as RefreshEnvelope
      const accessToken = payload.data?.access_token || ''
      const rotatedRefresh = payload.data?.refresh_token || ''
      if (!response.ok || !accessToken || !rotatedRefresh) {
        clearTenantSession()
        return null
      }
      localStorage.setItem('scheduler_pro_access_token', accessToken)
      localStorage.setItem('scheduler_pro_refresh_token', rotatedRefresh)
      window.dispatchEvent(new CustomEvent('scheduler-pro-session-refreshed'))
      return accessToken
    } catch {
      return null
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

function requestUrl(input: RequestInfo | URL): URL {
  if (input instanceof Request) return new URL(input.url, window.location.origin)
  return new URL(String(input), window.location.origin)
}

function withCurrentAuthorization(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  token: string,
): [RequestInfo | URL, RequestInit | undefined] {
  const forceFresh: RequestInit = { ...init, cache: 'no-store' }
  if (!token) return [input, forceFresh]
  if (input instanceof Request) {
    const headers = new Headers(input.headers)
    headers.set('Authorization', `Bearer ${token}`)
    headers.set('Cache-Control', 'no-cache')
    return [new Request(input, { headers, cache: 'no-store' }), forceFresh]
  }
  const headers = new Headers(init?.headers || {})
  headers.set('Authorization', `Bearer ${token}`)
  headers.set('Cache-Control', 'no-cache')
  return [input, { ...forceFresh, headers }]
}

export function installTenantAuthFetch(): void {
  if (installed) return
  installed = true
  const nativeFetch = window.fetch.bind(window)

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = requestUrl(input)
    if (!isSchedulerApi(url) || isAuthBootstrap(url)) {
      return nativeFetch(input, init)
    }

    const accessToken = currentAccessToken()
    const [authorizedInput, authorizedInit] = withCurrentAuthorization(
      input,
      init,
      accessToken,
    )
    let response = await nativeFetch(authorizedInput, authorizedInit)
    if (response.status !== 401 || !currentRefreshToken()) return response

    const renewedAccessToken = await refreshAccessToken(nativeFetch)
    if (!renewedAccessToken) {
      window.dispatchEvent(
        new CustomEvent('scheduler-pro-realtime-unauthorized', {
          detail: { status: 401, reason: 'refresh_failed' },
        }),
      )
      return response
    }

    const [retryInput, retryInit] = withCurrentAuthorization(
      input,
      init,
      renewedAccessToken,
    )
    response = await nativeFetch(retryInput, retryInit)
    return response
  }
}
