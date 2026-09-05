export type TenantRealtimeEvent = {
  sequence: number
  id: string
  event_type: string
  appointment_id?: string | null
  title: string
  message: string
  payload?: Record<string, unknown>
  created_at?: string
}

export type RealtimeConnectionState = 'idle' | 'connecting' | 'connected' | 'disconnected'

type RealtimeOptions = {
  apiBase: string
  token: string
  after?: number
  onEvent: (event: TenantRealtimeEvent) => void | Promise<void>
  onState?: (state: RealtimeConnectionState) => void
  onSequence?: (sequence: number) => void
}

type ApiEnvelope<T> = { data: T }
type PushKeyResponse = { public_key: string }

function authHeaders(token: string): HeadersInit {
  return {
    Accept: 'application/json',
    Authorization: `Bearer ${token}`,
  }
}

export function base64UrlToUint8Array(value: string): Uint8Array {
  const padding = '='.repeat((4 - (value.length % 4)) % 4)
  const base64 = (value + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const output = new Uint8Array(raw.length)
  for (let index = 0; index < raw.length; index += 1) output[index] = raw.charCodeAt(index)
  return output
}

async function jsonApi<T>(url: string, token: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      ...authHeaders(token),
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init.headers || {}),
    },
  })
  const payload = await response.json().catch(() => ({})) as Partial<ApiEnvelope<T>> & { error?: { message?: string } }
  if (!response.ok) throw new Error(payload.error?.message || `Falha HTTP ${response.status}`)
  return payload.data as T
}

export async function pushSubscriptionEnabled(): Promise<boolean> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return false
  const registration = await navigator.serviceWorker.ready
  return Boolean(await registration.pushManager.getSubscription())
}

export async function enableWebPush(
  apiBase: string,
  token: string,
  deviceLabel?: string,
): Promise<PushSubscription> {
  if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) {
    throw new Error('Este navegador não oferece Web Push/PWA.')
  }

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') throw new Error('Permissão de notificações não concedida.')

  const { public_key: publicKey } = await jsonApi<PushKeyResponse>(`${apiBase}/realtime/push/public-key`, token)
  const registration = await navigator.serviceWorker.ready
  let subscription = await registration.pushManager.getSubscription()
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: base64UrlToUint8Array(publicKey),
    })
  }

  const serialized = subscription.toJSON()
  if (!serialized.endpoint || !serialized.keys?.p256dh || !serialized.keys?.auth) {
    throw new Error('Assinatura push inválida retornada pelo navegador.')
  }

  await jsonApi(`${apiBase}/realtime/push/subscriptions`, token, {
    method: 'POST',
    body: JSON.stringify({
      endpoint: serialized.endpoint,
      expirationTime: serialized.expirationTime ?? null,
      keys: serialized.keys,
      device_label: deviceLabel || `${navigator.platform || 'Web'} / ${navigator.userAgent.slice(0, 80)}`,
    }),
  })
  return subscription
}

export async function disableWebPush(apiBase: string, token: string): Promise<void> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return
  const registration = await navigator.serviceWorker.ready
  const subscription = await registration.pushManager.getSubscription()
  if (!subscription) return
  await jsonApi(`${apiBase}/realtime/push/subscriptions`, token, {
    method: 'DELETE',
    body: JSON.stringify({ endpoint: subscription.endpoint }),
  }).catch(() => undefined)
  await subscription.unsubscribe()
}

export function startRealtimeStream(options: RealtimeOptions): () => void {
  let stopped = false
  let controller: AbortController | null = null
  let retryTimer: number | undefined
  let cursor = Math.max(options.after || 0, 0)
  let failures = 0

  const scheduleRetry = () => {
    if (stopped) return
    options.onState?.('disconnected')
    failures += 1
    const delay = Math.min(30_000, 2_500 * Math.max(1, failures))
    retryTimer = window.setTimeout(() => { void connect() }, delay)
  }

  const parseBlock = async (block: string) => {
    if (!block.trim() || block.trim().startsWith(':')) return
    let id = 0
    let data = ''
    for (const line of block.split('\n')) {
      if (line.startsWith('id:')) id = Number(line.slice(3).trim()) || 0
      if (line.startsWith('data:')) data += line.slice(5).trim()
    }
    if (!data) return
    const event = JSON.parse(data) as TenantRealtimeEvent
    const sequence = id || Number(event.sequence || 0)
    if (sequence > cursor) {
      cursor = sequence
      options.onSequence?.(cursor)
    }
    await options.onEvent(event)
  }

  const connect = async () => {
    if (stopped) return
    options.onState?.('connecting')
    controller = new AbortController()
    try {
      const response = await fetch(`${options.apiBase}/realtime/events?after=${cursor}`, {
        headers: {
          Accept: 'text/event-stream',
          Authorization: `Bearer ${options.token}`,
        },
        cache: 'no-store',
        signal: controller.signal,
      })

      if (response.status === 401) {
        stopped = true
        options.onState?.('disconnected')
        window.dispatchEvent(new CustomEvent('scheduler-pro-realtime-unauthorized', {
          detail: { status: response.status },
        }))
        return
      }
      if (response.status === 403) {
        // A permission/2FA denial is not an expired session; stop this stream,
        // without logging out the user or retrying a forbidden operation forever.
        stopped = true
        options.onState?.('disconnected')
        return
      }
      if (!response.ok || !response.body) throw new Error(`Realtime HTTP ${response.status}`)

      failures = 0
      options.onState?.('connected')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (!stopped) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
        let boundary = buffer.indexOf('\n\n')
        while (boundary >= 0) {
          const block = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          await parseBlock(block)
          boundary = buffer.indexOf('\n\n')
        }
      }
      if (!stopped) scheduleRetry()
    } catch (error) {
      if (!stopped && (error as Error).name !== 'AbortError') scheduleRetry()
    }
  }

  void connect()

  return () => {
    stopped = true
    controller?.abort()
    if (retryTimer !== undefined) window.clearTimeout(retryTimer)
    options.onState?.('idle')
  }
}
