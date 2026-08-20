const STORAGE_KEY = 'scheduler_pro_mobile_instance_v2'
const LEGACY_STORAGE_KEY = 'scheduler_pro_mobile_instance_url'
const LEGACY_API_BASE = (import.meta.env.VITE_API_BASE_URL || 'https://scheduler.argws.com.br/api/v1').replace(/\/$/, '')
const CONFIG_VERSION = 2 as const

type InstanceConfig = {
  version: typeof CONFIG_VERSION
  origin: string
  tenantId: string
  hostname: string
  validatedAt: string
}

type BrandingProbe = {
  data?: {
    tenant?: {
      id?: string | null
      hostname?: string | null
      slug?: string | null
    }
  }
}

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
  if (!configuredOrigin) throw new Error('Instância do tenant ainda não configurada.')
  return `${configuredOrigin}/api/v1`
}

function rewriteUrl(value: string): string {
  if (value.startsWith(LEGACY_API_BASE)) {
    if (!configuredOrigin) throw new Error('Informe a URL do tenant antes de acessar a plataforma.')
    return `${configuredApiBase()}${value.slice(LEGACY_API_BASE.length)}`
  }
  return value
}

function requestInitFrom(input: Request): RequestInit {
  const init: RequestInit = {
    method: input.method,
    headers: input.headers,
    credentials: input.credentials,
    mode: input.mode,
    cache: input.cache,
    redirect: input.redirect,
    referrer: input.referrer,
    referrerPolicy: input.referrerPolicy,
    integrity: input.integrity,
    keepalive: input.keepalive,
    signal: input.signal,
  }
  if (!['GET', 'HEAD'].includes(input.method.toUpperCase()) && input.body) init.body = input.body
  return init
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
      if (rewritten !== input.url) return originalFetch(rewritten, { ...requestInitFrom(input), ...(init || {}) })
    }
    return originalFetch(input, init)
  }) as typeof window.fetch
}

async function probeTenant(origin: string): Promise<InstanceConfig> {
  const fetcher = originalFetch || window.fetch.bind(window)
  const ready = await fetcher(`${origin}/api/v1/health/ready`, {
    headers: { Accept: 'application/json' },
  })
  if (!ready.ok) throw new Error(`A instância respondeu HTTP ${ready.status}.`)

  const manifestResponse = await fetcher(`${origin}/api/v1/branding/manifest`, {
    headers: { Accept: 'application/json' },
  })
  if (!manifestResponse.ok) {
    throw new Error('A URL respondeu, mas não foi reconhecida como uma instância de tenant do Scheduler Pro.')
  }
  const manifest = await manifestResponse.json().catch(() => ({})) as BrandingProbe
  const tenantId = String(manifest.data?.tenant?.id || '').trim()
  const hostname = String(manifest.data?.tenant?.hostname || new URL(origin).hostname).trim()
  if (!tenantId) {
    throw new Error('Use a URL exclusiva do seu tenant, não o domínio principal da plataforma.')
  }

  return {
    version: CONFIG_VERSION,
    origin,
    tenantId,
    hostname,
    validatedAt: new Date().toISOString(),
  }
}

function readSavedConfig(): InstanceConfig | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<InstanceConfig>
    if (parsed.version !== CONFIG_VERSION || !parsed.origin || !parsed.tenantId) return null
    return {
      version: CONFIG_VERSION,
      origin: normalizeOrigin(parsed.origin),
      tenantId: String(parsed.tenantId),
      hostname: String(parsed.hostname || new URL(parsed.origin).hostname),
      validatedAt: String(parsed.validatedAt || ''),
    }
  } catch {
    return null
  }
}

function clearTenantSession(): void {
  localStorage.removeItem('scheduler_pro_mobile_access_token')
  localStorage.removeItem('scheduler_pro_mobile_refresh_token')
  localStorage.removeItem('scheduler_pro_mobile_email')
}

function renderSetup(): Promise<InstanceConfig> {
  return new Promise((resolve) => {
    document.body.innerHTML = `
      <main id="sp-mobile-instance-setup">
        <section class="sp-instance-card">
          <div class="sp-instance-mark">SP</div>
          <p class="sp-instance-eyebrow">Scheduler Pro Mobile</p>
          <h1>Conectar à sua empresa</h1>
          <p>Informe a URL exclusiva do seu tenant. Você fará isso somente no primeiro uso ou quando escolher trocar de empresa.</p>
          <form id="sp-instance-form">
            <label>URL do tenant<input id="sp-instance-url" type="url" inputmode="url" autocomplete="url" placeholder="https://empresa.scheduler.argws.com.br" required /></label>
            <p class="sp-instance-hint">Exemplo: https://minhaempresa.scheduler.argws.com.br</p>
            <p id="sp-instance-error" role="alert"></p>
            <button id="sp-instance-submit" type="submit">Validar e continuar</button>
          </form>
        </section>
      </main>
      <style>
        html,body{margin:0;min-height:100%;background:#07182f;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}#sp-mobile-instance-setup{min-height:100dvh;display:grid;align-items:center;padding:max(24px,env(safe-area-inset-top)) 18px max(28px,env(safe-area-inset-bottom));background:radial-gradient(circle at 85% 10%,rgba(6,182,212,.22),transparent 32%),linear-gradient(180deg,#0c2244,#07182f)}.sp-instance-card{background:#fff;border-radius:26px;padding:28px 22px;color:#10213b;box-shadow:0 28px 70px rgba(0,0,0,.3);max-width:520px;width:100%;box-sizing:border-box;margin:auto}.sp-instance-mark{width:62px;height:62px;border-radius:20px;display:grid;place-items:center;background:linear-gradient(135deg,#2563eb,#06b6d4);color:#fff;font-size:22px;font-weight:900}.sp-instance-eyebrow{margin:22px 0 8px;color:#2563eb;text-transform:uppercase;letter-spacing:.16em;font-size:11px;font-weight:900}.sp-instance-card h1{font-size:31px;line-height:1.08;margin:0}.sp-instance-card>p:not(.sp-instance-eyebrow){color:#66768d;line-height:1.6}.sp-instance-card form{display:grid;gap:13px;margin-top:24px}.sp-instance-card label{display:grid;gap:8px;font-size:13px;font-weight:850}.sp-instance-card input{width:100%;box-sizing:border-box;height:54px;border:1px solid #dbe5f0;border-radius:15px;padding:0 14px;font-size:16px;outline:0}.sp-instance-card input:focus{border-color:#2563eb;box-shadow:0 0 0 4px rgba(37,99,235,.09)}.sp-instance-card button{height:54px;border:0;border-radius:15px;background:linear-gradient(135deg,#2563eb,#06b6d4);color:#fff;font-size:16px;font-weight:900}.sp-instance-card button:disabled{opacity:.6}.sp-instance-hint{margin:-2px 0 0!important;font-size:12px;color:#8090a6!important}#sp-instance-error{display:none;margin:0;padding:11px 12px;border-radius:12px;background:#fef2f2;border:1px solid #fecaca;color:#b91c1c;font-size:13px}
      </style>`

    const form = document.querySelector<HTMLFormElement>('#sp-instance-form')!
    const input = document.querySelector<HTMLInputElement>('#sp-instance-url')!
    const error = document.querySelector<HTMLParagraphElement>('#sp-instance-error')!
    const submit = document.querySelector<HTMLButtonElement>('#sp-instance-submit')!
    form.addEventListener('submit', async (event) => {
      event.preventDefault()
      error.style.display = 'none'
      submit.disabled = true
      submit.textContent = 'Validando tenant...'
      try {
        const origin = normalizeOrigin(input.value)
        const config = await probeTenant(origin)
        clearTenantSession()
        localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
        localStorage.removeItem(LEGACY_STORAGE_KEY)
        resolve(config)
      } catch (exc) {
        error.textContent = exc instanceof Error ? exc.message : 'Não foi possível validar a instância.'
        error.style.display = 'block'
        submit.disabled = false
        submit.textContent = 'Validar e continuar'
      }
    })
  })
}

export async function prepareMobileRuntimeInstance(): Promise<void> {
  installRuntimeFetch()

  // A chave antiga aceitava silenciosamente o domínio principal da plataforma.
  // Ela é deliberadamente ignorada para que instalações atualizadas peçam o tenant uma vez.
  if (localStorage.getItem(LEGACY_STORAGE_KEY)) localStorage.removeItem(LEGACY_STORAGE_KEY)

  const saved = readSavedConfig()
  if (saved) {
    configuredOrigin = saved.origin
    return
  }

  localStorage.removeItem(STORAGE_KEY)
  configuredOrigin = ''
  const config = await renderSetup()
  configuredOrigin = config.origin
  document.body.innerHTML = '<div id="app"></div>'
}

export function currentMobileInstanceOrigin(): string {
  return configuredOrigin
}

export function currentMobileApiBase(): string {
  return configuredApiBase()
}

export function resetMobileRuntimeInstance(): void {
  configuredOrigin = ''
  localStorage.removeItem(STORAGE_KEY)
  localStorage.removeItem(LEGACY_STORAGE_KEY)
  clearTenantSession()
  window.location.reload()
}
