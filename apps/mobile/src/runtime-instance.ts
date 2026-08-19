const STORAGE_KEY = 'scheduler_pro_mobile_instance_url'
const DEFAULT_API_BASE = (import.meta.env.VITE_API_BASE_URL || 'https://scheduler.argws.com.br/api/v1').replace(/\/$/, '')

let configuredOrigin = ''
let installed = false
let originalFetch: typeof window.fetch | null = null

function normalizeOrigin(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) throw new Error('Informe a URL do seu Scheduler Pro.')
  const parsed = new URL(trimmed.includes('://') ? trimmed : `https://${trimmed}`)
  if (parsed.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(parsed.hostname)) {
    throw new Error('A instância deve utilizar HTTPS.')
  }
  parsed.search = ''
  parsed.hash = ''
  parsed.pathname = ''
  return parsed.origin
}

function configuredApiBase(): string {
  return `${configuredOrigin}/api/v1`
}

function rewriteUrl(value: string): string {
  if (!configuredOrigin) return value
  if (value.startsWith(DEFAULT_API_BASE)) return `${configuredApiBase()}${value.slice(DEFAULT_API_BASE.length)}`
  return value
}

export function installRuntimeFetch(): void {
  if (installed) return
  installed = true
  originalFetch = window.fetch.bind(window)
  window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    if (!originalFetch) throw new Error('Fetch runtime indisponível.')
    if (typeof input === 'string') return originalFetch(rewriteUrl(input), init)
    if (input instanceof URL) return originalFetch(new URL(rewriteUrl(input.toString())), init)
    if (input instanceof Request) {
      const rewritten = rewriteUrl(input.url)
      if (rewritten !== input.url) return originalFetch(new Request(rewritten, input), init)
    }
    return originalFetch(input, init)
  }) as typeof window.fetch
}

async function probe(origin: string): Promise<void> {
  const fetcher = originalFetch || window.fetch.bind(window)
  const response = await fetcher(`${origin}/api/v1/health/ready`, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new Error(`A instância respondeu HTTP ${response.status}.`)
}

function renderSetup(): Promise<string> {
  return new Promise((resolve) => {
    document.body.innerHTML = `
      <main id="sp-mobile-instance-setup">
        <section class="sp-instance-card">
          <div class="sp-instance-mark">SP</div>
          <p class="sp-instance-eyebrow">Scheduler Pro Mobile</p>
          <h1>Conectar à sua empresa</h1>
          <p>Informe a URL do tenant uma única vez. Este mesmo aplicativo pode ser instalado por qualquer cliente Scheduler Pro.</p>
          <form id="sp-instance-form">
            <label>URL da instância<input id="sp-instance-url" type="url" inputmode="url" autocomplete="url" placeholder="https://empresa.scheduler.argws.com.br" required /></label>
            <p id="sp-instance-error" role="alert"></p>
            <button id="sp-instance-submit" type="submit">Salvar e continuar</button>
          </form>
        </section>
      </main>
      <style>
        html,body{margin:0;min-height:100%;background:#07182f;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}#sp-mobile-instance-setup{min-height:100dvh;display:grid;align-items:center;padding:max(24px,env(safe-area-inset-top)) 18px max(28px,env(safe-area-inset-bottom));background:radial-gradient(circle at 85% 10%,rgba(6,182,212,.22),transparent 32%),linear-gradient(180deg,#0c2244,#07182f)}.sp-instance-card{background:#fff;border-radius:26px;padding:28px 22px;color:#10213b;box-shadow:0 28px 70px rgba(0,0,0,.3)}.sp-instance-mark{width:62px;height:62px;border-radius:20px;display:grid;place-items:center;background:linear-gradient(135deg,#2563eb,#06b6d4);color:#fff;font-size:22px;font-weight:900}.sp-instance-eyebrow{margin:22px 0 8px;color:#2563eb;text-transform:uppercase;letter-spacing:.16em;font-size:11px;font-weight:900}.sp-instance-card h1{font-size:31px;line-height:1.08;margin:0}.sp-instance-card>p:not(.sp-instance-eyebrow){color:#66768d;line-height:1.6}.sp-instance-card form{display:grid;gap:13px;margin-top:24px}.sp-instance-card label{display:grid;gap:8px;font-size:13px;font-weight:850}.sp-instance-card input{width:100%;box-sizing:border-box;height:54px;border:1px solid #dbe5f0;border-radius:15px;padding:0 14px;font-size:16px;outline:0}.sp-instance-card input:focus{border-color:#2563eb;box-shadow:0 0 0 4px rgba(37,99,235,.09)}.sp-instance-card button{height:54px;border:0;border-radius:15px;background:linear-gradient(135deg,#2563eb,#06b6d4);color:#fff;font-size:16px;font-weight:900}.sp-instance-card button:disabled{opacity:.6}#sp-instance-error{display:none;margin:0;padding:11px 12px;border-radius:12px;background:#fef2f2;border:1px solid #fecaca;color:#b91c1c;font-size:13px}
      </style>`

    const form = document.querySelector<HTMLFormElement>('#sp-instance-form')!
    const input = document.querySelector<HTMLInputElement>('#sp-instance-url')!
    const error = document.querySelector<HTMLParagraphElement>('#sp-instance-error')!
    const submit = document.querySelector<HTMLButtonElement>('#sp-instance-submit')!
    form.addEventListener('submit', async (event) => {
      event.preventDefault()
      error.style.display = 'none'
      submit.disabled = true
      submit.textContent = 'Validando...'
      try {
        const origin = normalizeOrigin(input.value)
        await probe(origin)
        localStorage.setItem(STORAGE_KEY, origin)
        resolve(origin)
      } catch (exc) {
        error.textContent = exc instanceof Error ? exc.message : 'Não foi possível validar a instância.'
        error.style.display = 'block'
        submit.disabled = false
        submit.textContent = 'Salvar e continuar'
      }
    })
  })
}

export async function prepareMobileRuntimeInstance(): Promise<void> {
  installRuntimeFetch()
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    try {
      configuredOrigin = normalizeOrigin(saved)
      return
    } catch {
      localStorage.removeItem(STORAGE_KEY)
    }
  }
  configuredOrigin = await renderSetup()
  document.body.innerHTML = '<div id="app"></div>'
}

export function currentMobileInstanceOrigin(): string {
  return configuredOrigin
}
