import { apiGet } from './api/client'

export type BrandingManifest = {
  tenant: { id: string; slug: string | null; hostname: string | null }
  app: { name: string; public_name: string; slogan?: string | null; locale: string; timezone: string }
  assets: { logo_url?: string | null; icon_url?: string | null; favicon_url?: string | null }
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

  const favicon = manifest.assets.favicon_url || manifest.assets.icon_url
  if (favicon) {
    let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    link.href = favicon
  }
}
