import { apiGet } from './api/client'

export type BrandingManifest = {
  tenant: { id: string; slug: string | null; hostname: string | null }
  app: { name: string; public_name: string; slogan?: string | null; locale: string; timezone: string }
  assets: { logo_url?: string | null; logo_dark_url?: string | null; icon_url?: string | null; favicon_url?: string | null }
  theme: {
    mode: 'light' | 'dark' | 'system'
    font_family: string
    border_radius: string
    colors: {
      primary: string
      secondary: string
      accent: string
      background: string
      text: string
    }
  }
  settings: Record<string, unknown>
  status: string
  published_at?: string | null
  branding_version?: number
}

const PLATFORM_LOGOS = new Set([
  '/branding/scheduler-pro-logo-light.png',
  '/branding/scheduler-pro-logo-dark.png',
])

function versionedAsset(url: string, version: number): string {
  if (!url || !version || url.startsWith('data:') || url.startsWith('blob:')) return url
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}v=${version}`
}

function cssAsset(url: string): string {
  return `url(${JSON.stringify(url)})`
}

function applySidebarBranding(manifest: BrandingManifest): void {
  const root = document.documentElement
  const version = Number(manifest.branding_version || 0)
  const primaryLogo = String(manifest.assets.logo_url || '').trim()
  const darkLogo = String(manifest.assets.logo_dark_url || '').trim()
  const icon = String(manifest.assets.icon_url || '').trim()
  const customPrimary = Boolean(primaryLogo && !PLATFORM_LOGOS.has(primaryLogo))
  const customDark = Boolean(darkLogo && !PLATFORM_LOGOS.has(darkLogo))
  const customLogo = customPrimary || customDark

  const desktopLogo = customDark
    ? darkLogo
    : customPrimary
      ? primaryLogo
      : darkLogo || '/branding/scheduler-pro-logo-dark.png'

  const mobileLogo = customPrimary
    ? primaryLogo
    : customDark
      ? darkLogo
      : icon || primaryLogo || '/icons/icon-512.png'

  root.dataset.tenantCustomLogo = customLogo ? 'true' : 'false'
  root.style.setProperty('--sp-sidebar-logo-desktop', cssAsset(versionedAsset(desktopLogo, version)))
  root.style.setProperty('--sp-sidebar-logo-mobile', cssAsset(versionedAsset(mobileLogo, version)))
}

export async function loadBrandingManifest(): Promise<BrandingManifest> {
  return apiGet<BrandingManifest>('/branding/manifest')
}

export function applyBranding(manifest: BrandingManifest): void {
  const root = document.documentElement
  root.style.setProperty('--sp-primary', manifest.theme.colors.primary)
  root.style.setProperty('--sp-secondary', manifest.theme.colors.secondary)
  root.style.setProperty('--sp-accent', manifest.theme.colors.accent)
  root.style.setProperty('--sp-background', manifest.theme.colors.background)
  root.style.setProperty('--sp-text', manifest.theme.colors.text)
  root.style.setProperty('--sp-radius', manifest.theme.border_radius)
  root.style.setProperty('--sp-font', manifest.theme.font_family)

  document.title = manifest.app.public_name || manifest.app.name
  root.dataset.tenantTheme = manifest.theme.mode || 'system'
  applySidebarBranding(manifest)

  const favicon = manifest.assets.favicon_url || manifest.assets.icon_url
  if (favicon) {
    let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    const version = Number(manifest.branding_version || 0)
    link.href = versionedAsset(favicon, version)
  }
}
