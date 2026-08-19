const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
const SESSION_KEY = 'scheduler-pro-admin-session'
const REDACT_KEY = /(password|passwd|secret|token|authorization|cookie|api[_-]?key|private[_-]?key)/i
const recentlySent = new Map<string, number>()

function accessToken(): string {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return ''
    const parsed = JSON.parse(raw) as { accessToken?: string }
    return parsed.accessToken || ''
  } catch {
    return ''
  }
}

function sanitize(value: unknown, depth = 0): unknown {
  if (depth > 5) return '[MAX_DEPTH]'
  if (value instanceof Error) {
    return {
      name: value.name,
      message: value.message,
      stack: value.stack?.slice(0, 12000),
    }
  }
  if (Array.isArray(value)) return value.slice(0, 50).map(item => sanitize(item, depth + 1))
  if (value && typeof value === 'object') {
    const result: Record<string, unknown> = {}
    for (const [key, item] of Object.entries(value as Record<string, unknown>).slice(0, 80)) {
      result[key] = REDACT_KEY.test(key) ? '[REDACTED]' : sanitize(item, depth + 1)
    }
    return result
  }
  if (typeof value === 'string') {
    return value
      .replace(/(Bearer\s+)[A-Za-z0-9._~+\-/=]+/gi, '$1[REDACTED]')
      .slice(0, 16000)
  }
  return value
}

export function captureFrontendEvent(
  level: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL',
  event: string,
  message: string,
  details: Record<string, unknown> = {},
): void {
  const token = accessToken()
  if (!token) return

  const signature = `${level}|${event}|${message}`.slice(0, 1000)
  const now = Date.now()
  const previous = recentlySent.get(signature) || 0
  if (now - previous < 5000) return
  recentlySent.set(signature, now)
  if (recentlySent.size > 300) {
    for (const [key, timestamp] of recentlySent) {
      if (now - timestamp > 60_000) recentlySent.delete(key)
    }
  }

  const body = {
    source: 'frontend',
    service: 'admin-web',
    level,
    event: event.slice(0, 160),
    message: message.slice(0, 16000),
    hostname: window.location.hostname,
    details: sanitize({
      ...details,
      href: window.location.href,
      userAgent: navigator.userAgent,
      online: navigator.onLine,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
    }),
  }

  void fetch(`${API_BASE_URL}/platform/observability/logs/ingest`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
    keepalive: true,
  }).catch(() => undefined)
}

export function installFrontendTelemetry(): void {
  window.addEventListener('error', event => {
    captureFrontendEvent('ERROR', 'browser_error', event.message || 'Erro JavaScript no navegador.', {
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
      error: sanitize(event.error),
    })
  })

  window.addEventListener('unhandledrejection', event => {
    const reason = event.reason
    captureFrontendEvent(
      'ERROR',
      'unhandled_rejection',
      reason instanceof Error ? reason.message : String(reason || 'Promise rejeitada sem tratamento.'),
      { reason: sanitize(reason) },
    )
  })

  const originalError = console.error.bind(console)
  const originalWarn = console.warn.bind(console)
  console.error = (...args: unknown[]) => {
    originalError(...args)
    captureFrontendEvent('ERROR', 'console_error', args.map(item => String(item)).join(' ').slice(0, 16000), {
      arguments: sanitize(args),
    })
  }
  console.warn = (...args: unknown[]) => {
    originalWarn(...args)
    captureFrontendEvent('WARNING', 'console_warning', args.map(item => String(item)).join(' ').slice(0, 16000), {
      arguments: sanitize(args),
    })
  }
}
