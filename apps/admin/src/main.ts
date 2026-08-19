import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './AdminControlPlane.vue'
import TenantManagementDrawer from './TenantManagementDrawer.vue'
import { installDiagnosticsDownload } from './diagnostics-download'
import { installFrontendTelemetry } from './frontend-telemetry'
import { installVersionBadge } from './version-badge'
import './styles.css'
import './operational.css'
import './hubfiscal-admin.css'
import './enterprise.css'
import './branding.css'
import './pwa'

installFrontendTelemetry()

createApp(App).use(createPinia()).mount('#app')
installDiagnosticsDownload()
installVersionBadge()

const tenantManagerHost = document.createElement('div')
tenantManagerHost.id = 'scheduler-pro-tenant-manager'
document.body.appendChild(tenantManagerHost)
createApp(TenantManagementDrawer).mount(tenantManagerHost)
