export class SchedulerProClient {
  constructor(private readonly baseUrl: string, private readonly token?: string) {}

  async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, { headers: this.headers() })
    if (!response.ok) throw new Error(`Scheduler Pro API error ${response.status}`)
    const payload = await response.json()
    return payload.data as T
  }

  private headers(): HeadersInit {
    return this.token ? { Authorization: `Bearer ${this.token}`, Accept: 'application/json' } : { Accept: 'application/json' }
  }
}
