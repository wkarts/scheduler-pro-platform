const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
const SESSION_KEY = 'scheduler-pro-admin-session'
const BUTTON_ID = 'scheduler-pro-download-diagnostics'

function token(): string {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return ''
    return (JSON.parse(raw) as { accessToken?: string }).accessToken || ''
  } catch {
    return ''
  }
}

function filenameFromDisposition(value: string | null): string {
  const match = value?.match(/filename="?([^";]+)"?/i)
  return match?.[1] || `scheduler-pro-diagnostics-${new Date().toISOString().replace(/[:.]/g, '-')}.zip`
}

async function download(button: HTMLButtonElement): Promise<void> {
  const accessToken = token()
  if (!accessToken) return

  button.disabled = true
  const previous = button.textContent
  button.textContent = 'Coletando logs...'
  try {
    const tenantSelect = document.querySelector<HTMLSelectElement>('.company-switcher select')
    const params = new URLSearchParams()
    if (tenantSelect?.value) params.set('tenant', tenantSelect.value)
    const encoded = params.toString()
    const query = encoded ? `?${encoded}` : ''
    const response = await fetch(`${API_BASE_URL}/platform/observability/logs/export${query}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { error?: { message?: string } }
      throw new Error(payload.error?.message || `Falha HTTP ${response.status}`)
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filenameFromDisposition(response.headers.get('Content-Disposition'))
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
    button.textContent = 'Download concluído'
    window.setTimeout(() => { button.textContent = previous }, 2500)
  } catch (error) {
    console.error('Falha ao baixar diagnóstico completo', error)
    button.textContent = error instanceof Error ? error.message.slice(0, 80) : 'Falha no download'
    window.setTimeout(() => { button.textContent = previous }, 4000)
  } finally {
    button.disabled = false
  }
}

function ensureButton(): void {
  const toolbar = document.querySelector<HTMLElement>('.observability-toolbar')
  const existing = document.getElementById(BUTTON_ID)
  if (!toolbar) {
    existing?.remove()
    return
  }
  if (existing) return

  const container = document.createElement('div')
  container.id = BUTTON_ID
  container.style.display = 'flex'
  container.style.justifyContent = 'flex-end'
  container.style.marginTop = '10px'

  const button = document.createElement('button')
  button.type = 'button'
  button.className = 'btn'
  button.textContent = 'Baixar logs completos (.zip)'
  button.title = 'Inclui plataforma, tenant, auditoria, provisionamento, Docker/console e erros do frontend; segredos são redigidos.'
  button.addEventListener('click', () => { void download(button) })
  container.appendChild(button)
  toolbar.appendChild(container)
}

export function installDiagnosticsDownload(): void {
  ensureButton()
  const observer = new MutationObserver(ensureButton)
  observer.observe(document.body, { childList: true, subtree: true })
}
