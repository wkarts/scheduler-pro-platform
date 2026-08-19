import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './AdminControlPlane.vue'
import TenantManagementDrawer from './TenantManagementDrawer.vue'
import TenantLogInspector from './TenantLogInspector.vue'
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

const tenantLogHost = document.createElement('div')
tenantLogHost.id = 'scheduler-pro-tenant-log-inspector'
document.body.appendChild(tenantLogHost)
createApp(TenantLogInspector).mount(tenantLogHost)
