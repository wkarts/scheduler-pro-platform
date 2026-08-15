export type ApiResponse<T> = { data: T; meta: Record<string, unknown> }
export type TenantContext = { tenant_id: string; slug: string; hostname: string; timezone: string }
export type AppointmentStatus = 'PENDING'|'AWAITING_CONFIRMATION'|'CONFIRMED'|'CHECKED_IN'|'IN_PROGRESS'|'COMPLETED'|'CANCELLED'|'NO_SHOW'

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
  status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED' | string
  published_at?: string | null
}

export type BuildProfile = {
  id: string
  tenant_id: string
  branding_profile_id?: string | null
  name: string
  target: 'web' | 'desktop' | 'android' | 'ios' | 'pwa'
  bundle_identifier?: string | null
  package_name?: string | null
  api_url: string
  features: string[]
  config: Record<string, unknown>
}
