export const projectConfig = {
  app: {
    name: 'Scheduler Pro',
    productName: 'Scheduler Pro Mobile',
    identifier: 'br.com.argws.schedulerpro',
    version: '0.1.0-alpha.1',
    apiUrl: import.meta.env.VITE_API_BASE_URL || 'https://scheduler.argws.com.br/api/v1'
  },
  features: {
    licensing: false,
    telemetry: false,
    localCache: true,
    whatsapp: true,
    landing: true,
    whiteLabel: true,
    builds: true,
    headlessMode: false,
    webhookService: false,
    websocketService: false
  },
  runtime: {
    mode: 'mobile',
    source: 'template-app-tauri-desktop-main'
  }
}
export const appFeatures = projectConfig.features
