type TelemetryLevel = 'INFO' | 'WARNING' | 'ERROR'

type TelemetryDetails = Record<string, unknown>

function accessToken(): string {
  return localStorage.getItem('scheduler_pro_access_token') || ''
}

export async function sendTenantTelemetry(
  event: string,
  message: string,
  level: TelemetryLevel = 'INFO',
  details: TelemetryDetails = {},
): Promise<void> {
  const token = accessToken()
  if (!token) return
  try {
    await fetch('/api/v1/telemetry/events', {
      method: 'POST',
      headers: {
        accept: 'application/json',
        'content-type': 'application/json',
        authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ level, event, message, details }),
      keepalive: true,
      cache: 'no-store',
    })
  } catch {
    // Telemetry must never make the tenant UI fail.
  }
}

function errorDetails(error: unknown): TelemetryDetails {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      stack: error.stack?.slice(0, 8000),
      hash: window.location.hash,
      path: window.location.pathname,
    }
  }
  return { value: String(error).slice(0, 2000), hash: window.location.hash }
}

function trackAgendaTabClick(event: Event): void {
  const target = event.target as Element | null
  const button = target?.closest('.sp-agenda-ops > nav button') as HTMLButtonElement | null
  if (!button) return
  const tab = button.textContent?.trim() || 'desconhecida'
  const startedAt = performance.now()
  void sendTenantTelemetry(
    'agenda_advanced_tab_opening',
    `Abrindo a guia ${tab} da operação avançada.`,
    'INFO',
    { tab, viewport_width: window.innerWidth, viewport_height: window.innerHeight },
  )
  window.setTimeout(() => {
    void sendTenantTelemetry(
      'agenda_advanced_ui_responsive',
      `A interface permaneceu responsiva após abrir a guia ${tab}.`,
      'INFO',
      { tab, elapsed_ms: Math.round(performance.now() - startedAt) },
    )
  }, 750)
}

export function installTenantFrontendTelemetry(): () => void {
  const onError = (event: ErrorEvent): void => {
    void sendTenantTelemetry(
      'browser_error',
      event.message || 'Erro JavaScript no WebApp do tenant.',
      'ERROR',
      {
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        ...errorDetails(event.error),
      },
    )
  }
  const onUnhandledRejection = (event: PromiseRejectionEvent): void => {
    void sendTenantTelemetry(
      'browser_unhandled_rejection',
      'Uma operação assíncrona do WebApp falhou sem tratamento.',
      'ERROR',
      errorDetails(event.reason),
    )
  }

  window.addEventListener('error', onError)
  window.addEventListener('unhandledrejection', onUnhandledRejection)
  document.addEventListener('click', trackAgendaTabClick, true)

  let observer: PerformanceObserver | undefined
  if ('PerformanceObserver' in window) {
    try {
      let lastReported = 0
      observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.duration < 1000 || performance.now() - lastReported < 5000) continue
          lastReported = performance.now()
          void sendTenantTelemetry(
            'browser_long_task',
            'O navegador ficou ocupado por uma tarefa longa.',
            'WARNING',
            {
              duration_ms: Math.round(entry.duration),
              name: entry.name,
              hash: window.location.hash,
              viewport_width: window.innerWidth,
            },
          )
        }
      })
      observer.observe({ entryTypes: ['longtask'] })
    } catch {
      observer = undefined
    }
  }

  return () => {
    window.removeEventListener('error', onError)
    window.removeEventListener('unhandledrejection', onUnhandledRejection)
    document.removeEventListener('click', trackAgendaTabClick, true)
    observer?.disconnect()
  }
}
