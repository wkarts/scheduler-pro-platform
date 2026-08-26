const STATUS_PATH = '/api/v1/integrations/whatsapp/status'
const LEGACY_STATUS_PATH = '/api/v1/integrations/whatsapp/status/legacy'

let installed = false
let visualScheduled = false

function hasExplicitAuthorization(headers?: HeadersInit): boolean {
  if (!headers) return false
  try {
    return new Headers(headers).has('authorization')
  } catch {
    return false
  }
}

function rewriteLegacyStatus(input: RequestInfo | URL, init?: RequestInit): RequestInfo | URL {
  // TenantConsole é o consumidor histórico e inclui o Authorization explicitamente
  // em cada chamada. O novo Centro de Configurações usa o fetch autenticado global
  // e deve continuar consumindo o contrato novo em /status.
  if (!hasExplicitAuthorization(init?.headers)) return input

  if (typeof input === 'string') {
    try {
      const url = new URL(input, window.location.origin)
      if (url.pathname !== STATUS_PATH) return input
      url.pathname = LEGACY_STATUS_PATH
      return input.startsWith('http') ? url.toString() : `${url.pathname}${url.search}${url.hash}`
    } catch {
      return input
    }
  }

  if (input instanceof URL) {
    if (input.pathname !== STATUS_PATH) return input
    const url = new URL(input.toString())
    url.pathname = LEGACY_STATUS_PATH
    return url
  }

  if (input instanceof Request) {
    const url = new URL(input.url)
    if (url.pathname !== STATUS_PATH) return input
    url.pathname = LEGACY_STATUS_PATH
    return new Request(url.toString(), input)
  }

  return input
}

function scheduleVisualNormalization(): void {
  if (visualScheduled) return
  visualScheduled = true
  queueMicrotask(() => {
    visualScheduled = false
    normalizeVisibleProviderLabels()
  })
}

function normalizeVisibleProviderLabels(): void {
  const root = document.querySelector('.tenant-console')
  if (!root) return
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const nodes: Text[] = []
  let node = walker.nextNode()
  while (node) {
    if (node instanceof Text) nodes.push(node)
    node = walker.nextNode()
  }
  for (const textNode of nodes) {
    const parent = textNode.parentElement
    if (!parent || parent.closest('code,pre,script,style,[data-provider-technical]')) continue
    const next = textNode.data
      .replace(/ARGWS\s+WhatsApp\s+API/gi, 'WhatsApp')
      .replace(/Evolution\s+API/gi, 'WhatsApp')
      .replace(/WhatsApp\s+API/gi, 'WhatsApp')
    if (next !== textNode.data) textNode.data = next
  }
}

export function installWhatsAppCompatibilityRuntime(): void {
  if (installed || typeof window === 'undefined') return
  installed = true

  const authenticatedFetch = window.fetch.bind(window)
  window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    return authenticatedFetch(rewriteLegacyStatus(input, init), init)
  }) as typeof window.fetch

  const observer = new MutationObserver(scheduleVisualNormalization)
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true })
  scheduleVisualNormalization()
}
