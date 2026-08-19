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

const MOBILE_QUERY = '(max-width: 700px)'

function annotateResponsiveTables(root: ParentNode = document): void {
  const tables = Array.from(root.querySelectorAll('.tenant-console .operational-table table')) as HTMLTableElement[]
  for (const table of tables) {
    const headerCells = Array.from(table.querySelectorAll('thead th')) as HTMLTableCellElement[]
    const labels = headerCells.map((cell) => cell.textContent?.trim() || '')
    const rows = Array.from(table.querySelectorAll('tbody tr')) as HTMLTableRowElement[]
    for (const row of rows) {
      Array.from(row.cells).forEach((cell, index) => {
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
  const elements = Array.from(root.querySelectorAll('.tenant-console .error-banner, .tenant-console .form-error, .tenant-console .sp-error'))
  for (const element of elements) humanizeErrorElement(element)
}

function optionSignature(select: HTMLSelectElement): string {
  return Array.from(select.options)
    .filter((option) => option.value)
    .map((option) => `${option.value}\u0000${option.textContent?.trim() || ''}\u0000${option.disabled ? '1' : '0'}`)
    .join('\u0001')
}

function syncTouchPicker(select: HTMLSelectElement, container: HTMLElement): void {
  const signature = optionSignature(select)
  const selected = select.value
  if (container.dataset.signature === signature && container.dataset.selected === selected) return

  const fragment = document.createDocumentFragment()
  const options = Array.from(select.options).filter((option) => option.value)
  for (const option of options) {
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'sp-mobile-option'
    button.dataset.value = option.value
    button.disabled = option.disabled
    button.classList.toggle('selected', selected === option.value)
    const label = option.textContent?.trim() || option.value
    const [name, ...details] = label.split('·').map((item) => item.trim())
    const strong = document.createElement('strong')
    strong.textContent = name || label
    const small = document.createElement('small')
    small.textContent = details.join(' · ') || 'Toque para selecionar'
    button.append(strong, small)
    button.addEventListener('click', () => {
      if (button.disabled) return
      select.value = option.value
      container.dataset.selected = option.value
      select.dispatchEvent(new Event('change', { bubbles: true }))
      const siblings = Array.from(container.querySelectorAll('.sp-mobile-option')) as HTMLElement[]
      for (const sibling of siblings) {
        sibling.classList.toggle('selected', sibling.dataset.value === option.value)
      }
    })
    fragment.appendChild(button)
  }
  container.replaceChildren(fragment)
  container.dataset.signature = signature
  container.dataset.selected = selected
}

function enhanceTouchSelects(root: ParentNode = document): void {
  if (!window.matchMedia(MOBILE_QUERY).matches) return
  const selects = Array.from(root.querySelectorAll('.sp-agenda-ops select[size]')) as HTMLSelectElement[]
  for (const select of selects) {
    select.size = Math.min(6, Math.max(2, select.options.length))
    const parent = select.parentElement
    if (!parent) continue
    let container = parent.querySelector(':scope > .sp-mobile-option-list') as HTMLElement | null
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
    const toggle = shell.querySelector('.topbar > .icon-button:first-child') as HTMLButtonElement | null
    toggle?.click()
    const mainContent = document.querySelector('.tenant-console .main-content') as HTMLElement | null
    mainContent?.focus({ preventScroll: true })
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
  let frame = 0
  const reconcile = (): void => {
    if (frame) return
    frame = window.requestAnimationFrame(() => {
      frame = 0
      annotateResponsiveTables()
      normalizeErrorPresentation()
      enhanceTouchSelects()
    })
  }

  const observer = new MutationObserver((mutations) => {
    // Ignore mutations generated by our own touch-picker buttons. Without this
    // guard, replaceChildren() could recursively wake the observer and saturate CPU/RAM.
    const meaningful = mutations.some((mutation) =>
      Array.from(mutation.addedNodes).some((node) => {
        if (!(node instanceof Element)) return false
        return !node.closest('.sp-mobile-option-list') && !node.classList.contains('sp-mobile-option-list')
      }),
    )
    if (meaningful) reconcile()
  })

  observer.observe(document.documentElement, { childList: true, subtree: true })
  document.addEventListener('click', closeMobileDrawerAfterNavigation, true)
  window.addEventListener('scheduler-pro-realtime-unauthorized', expireSession)
  window.addEventListener('resize', reconcile, { passive: true })
  reconcile()

  return () => {
    observer.disconnect()
    if (frame) window.cancelAnimationFrame(frame)
    document.removeEventListener('click', closeMobileDrawerAfterNavigation, true)
    window.removeEventListener('scheduler-pro-realtime-unauthorized', expireSession)
    window.removeEventListener('resize', reconcile)
  }
}
