export type ApiResponse<T> = { data: T; meta: Record<string, unknown> }

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

export class SchedulerProClient {
  constructor(private readonly baseUrl: string, private readonly token?: string) {}

  async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, { headers: this.headers() })
    if (!response.ok) throw new Error(`Scheduler Pro API error ${response.status}`)
    const payload = (await response.json()) as ApiResponse<T>
    return payload.data
  }

  async put<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'PUT',
      headers: { ...this.headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!response.ok) throw new Error(`Scheduler Pro API error ${response.status}`)
    const payload = (await response.json()) as ApiResponse<T>
    return payload.data
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { ...this.headers(), 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) throw new Error(`Scheduler Pro API error ${response.status}`)
    const payload = (await response.json()) as ApiResponse<T>
    return payload.data
  }

  brandingManifest(): Promise<BrandingManifest> {
    return this.get<BrandingManifest>('/branding/manifest')
  }

  saveBrandingProfile(payload: Partial<BrandingManifest['app']> & Record<string, unknown>): Promise<BrandingManifest> {
    return this.put<BrandingManifest>('/branding/profile', payload)
  }

  publishBrandingProfile(): Promise<BrandingManifest> {
    return this.post<BrandingManifest>('/branding/publish')
  }

  private headers(): HeadersInit {
    return this.token ? { Authorization: `Bearer ${this.token}`, Accept: 'application/json' } : { Accept: 'application/json' }
  }
}
