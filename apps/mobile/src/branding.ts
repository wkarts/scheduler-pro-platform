const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

export type BrandingManifest = {
  tenant: { id: string; slug: string | null; hostname: string | null }
  app: { name: string; public_name: string; slogan?: string | null; locale: string; timezone: string }
  assets: { logo_url?: string | null; icon_url?: string | null; favicon_url?: string | null }
  theme: {
    mode: 'light' | 'dark' | 'system'
    font_family: string
    border_radius: string
    colors: { primary: string; secondary: string; accent: string; background: string; text: string }
  }
  settings: Record<string, unknown>
  status: string
  published_at?: string | null
}

type ApiResponse<T> = { data: T; meta: Record<string, unknown> }

export async function loadBrandingManifest(): Promise<BrandingManifest | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/branding/manifest`, { headers: { Accept: 'application/json' } })
    if (!response.ok) return null
    const payload = (await response.json()) as ApiResponse<BrandingManifest>
    return payload.data
  } catch {
    return null
  }
}

export function applyBranding(manifest: BrandingManifest | null): void {
  if (!manifest) return
  const root = document.documentElement
  root.style.setProperty('--sp-primary', manifest.theme.colors.primary)
  root.style.setProperty('--sp-secondary', manifest.theme.colors.secondary)
  root.style.setProperty('--sp-accent', manifest.theme.colors.accent)
  root.style.setProperty('--sp-background', manifest.theme.colors.background)
  root.style.setProperty('--sp-text', manifest.theme.colors.text)
  root.style.setProperty('--sp-radius', manifest.theme.border_radius)
  root.style.setProperty('--sp-font', manifest.theme.font_family)
  document.title = manifest.app.public_name || manifest.app.name
}
