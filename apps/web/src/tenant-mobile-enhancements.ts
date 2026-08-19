const TECHNICAL_CODE = /\s*\(([A-Z][A-Z0-9_]{3,})\)\s*$/

const friendlyByCode: Record<string, string> = {
  INTERNAL_SERVER_ERROR: 'Não foi possível concluir esta operação agora. Tente novamente em instantes.',
  AUTH_INVALID_TOKEN: 'Sua sessão não é mais válida. Entre novamente.',
  AUTH_TOKEN_EXPIRED: 'Sua sessão expirou. Entre novamente.',
  AUTH_REQUIRED: 'Sua sessão expirou. Entre novamente.',
  TENANT_NOT_FOUND: 'Não foi possível localizar o ambiente desta empresa.',
  TENANT_SUSPENDED: 'Este ambiente está temporariamente suspenso. Fale com o administrador da plataforma.',
  APPOINTMENT_SLOT_UNAVAILABLE: 'Esse horário já está ocupado. Escolha outro horário.',
  APPOINTMENT_OUTSIDE_BUSINESS_HOURS: 'O horário escolhido está fora do expediente configurado.',
  APPOINTMENT_BLOCKED_PERIOD: 'O horário escolhido está bloqueado na agenda.',
}

function annotateResponsiveTables(root: ParentNode = document): void {
  const tables = root.querySelectorAll<HTMLTableElement>('.tenant-console .operational-table table')
  for (const table of tables) {
    const labels = [...table.querySelectorAll<HTMLTableCellElement>('thead th')].map((cell) => cell.textContent?.trim() || '')
    for (const row of table.querySelectorAll<HTMLTableRowElement>('tbody tr')) {
      ;[...row.cells].forEach((cell, index) => {
        if (!cell.dataset.label) cell.dataset.label = labels[index] || 'Detalhe'
      })
    }
  }
}

function humanizeErrorElement(element: Element): void {
  const raw = element.textContent?.trim()
  if (!raw) return
  const match = raw.match(TECHNICAL_CODE)
  if (!match) return
  const code = match[1]
  const replacement = friendlyByCode[code]
  if (replacement) {
    const prefix = raw.replace(TECHNICAL_CODE, '').replace(/Falha interna inesperada\.?/gi, '').trim()
    element.textContent = prefix ? `${prefix} ${replacement}` : replacement
  } else {
    element.textContent = raw.replace(TECHNICAL_CODE, '').trim()
  }
  element.setAttribute('data-error-code', code)
  element.setAttribute('title', `Código técnico: ${code}`)
}

function normalizeErrorPresentation(root: ParentNode = document): void {
  for (const element of root.querySelectorAll('.tenant-console .error-banner, .tenant-console .form-error, .tenant-console .sp-error')) {
    humanizeErrorElement(element)
  }
}

function syncTouchPicker(select: HTMLSelectElement, container: HTMLElement): void {
  const fragment = document.createDocumentFragment()
  const options = [...select.options].filter((option) => option.value)
  for (const option of options) {
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'sp-mobile-option'
    button.dataset.value = option.value
    button.classList.toggle('selected', select.value === option.value)
    const label = option.textContent?.trim() || option.value
    const [name, ...details] = label.split('·').map((item) => item.trim())
    const strong = document.createElement('strong')
    strong.textContent = name || label
    const small = document.createElement('small')
    small.textContent = details.join(' · ') || 'Toque para selecionar'
    button.append(strong, small)
    button.addEventListener('click', () => {
      select.value = option.value
      select.dispatchEvent(new Event('change', { bubbles: true }))
      for (const sibling of container.querySelectorAll('.sp-mobile-option')) {
        sibling.classList.toggle('selected', (sibling as HTMLElement).dataset.value === option.value)
      }
    })
    fragment.appendChild(button)
  }
  container.replaceChildren(fragment)
}

function enhanceTouchSelects(root: ParentNode = document): void {
  const selects = root.querySelectorAll<HTMLSelectElement>('.sp-agenda-ops select[size]')
  for (const select of selects) {
    select.size = Math.min(6, Math.max(2, select.options.length))
    const parent = select.parentElement
    if (!parent) continue
    let container = parent.querySelector<HTMLElement>(':scope > .sp-mobile-option-list')
    if (!container) {
      container = document.createElement('div')
      container.className = 'sp-mobile-option-list'
      parent.appendChild(container)
    }
    syncTouchPicker(select, container)
  }
}

function closeMobileDrawerAfterNavigation(event: Event): void {
  const target = event.target as Element | null
  if (!target?.closest('.tenant-console .nav-list .nav-item')) return
  if (!window.matchMedia('(max-width: 900px)').matches) return
  queueMicrotask(() => {
    const shell = document.querySelector('.tenant-console.mobileOpen')
    if (!shell) return
    const toggle = shell.querySelector<HTMLButtonElement>('.topbar > .icon-button:first-child')
    toggle?.click()
    document.querySelector<HTMLElement>('.tenant-console .main-content')?.focus({ preventScroll: true })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  })
}

function expireSession(): void {
  localStorage.removeItem('scheduler_pro_access_token')
  localStorage.removeItem('scheduler_pro_refresh_token')
  localStorage.removeItem('scheduler_pro_realtime_sequence')
  window.location.hash = '#dashboard'
  window.setTimeout(() => window.location.reload(), 10)
}

export function installTenantMobileEnhancements(): () => void {
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (!(node instanceof Element)) continue
        annotateResponsiveTables(node)
        normalizeErrorPresentation(node)
        enhanceTouchSelects(node)
      }
    }
    annotateResponsiveTables()
    normalizeErrorPresentation()
    enhanceTouchSelects()
  })

  observer.observe(document.documentElement, { childList: true, subtree: true })
  document.addEventListener('click', closeMobileDrawerAfterNavigation, true)
  window.addEventListener('scheduler-pro-realtime-unauthorized', expireSession)
  annotateResponsiveTables()
  normalizeErrorPresentation()
  enhanceTouchSelects()

  return () => {
    observer.disconnect()
    document.removeEventListener('click', closeMobileDrawerAfterNavigation, true)
    window.removeEventListener('scheduler-pro-realtime-unauthorized', expireSession)
  }
}
