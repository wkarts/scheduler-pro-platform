import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './AdminControlPlane.vue'
import AdminHtmlTemplateImportOverlay from './AdminHtmlTemplateImportOverlay.vue'
import AdminSecondFactorGate from './AdminSecondFactorGate.vue'
import AdminTemplateSupportCenter from './AdminTemplateSupportCenter.vue'
import TenantManagementDrawer from './TenantManagementDrawer.vue'
import { installDiagnosticsDownload } from './diagnostics-download'
import { installFrontendTelemetry } from './frontend-telemetry'
import { installVersionBadge } from './version-badge'
import './styles.css'
import './operational.css'
import './hubfiscal-admin.css'
import './enterprise.css'
import './branding.css'
import './scrollbars.css'
import './pwa'

installFrontendTelemetry()

createApp(App).use(createPinia()).mount('#app')
installDiagnosticsDownload()
installVersionBadge()

const tenantManagerHost = document.createElement('div')
tenantManagerHost.id = 'scheduler-pro-tenant-manager'
document.body.appendChild(tenantManagerHost)
createApp(TenantManagementDrawer).mount(tenantManagerHost)

const templateSupportHost = document.createElement('div')
templateSupportHost.id = 'scheduler-pro-template-support'
document.body.appendChild(templateSupportHost)
createApp(AdminTemplateSupportCenter).mount(templateSupportHost)

// A autoria externa de novos modelos é HTML-first. O importador JSON legado
// continua disponível no backend por compatibilidade, mas deixa de ser uma
// segunda porta visual concorrente no Control Plane.
const htmlTemplateImportHost = document.createElement('div')
htmlTemplateImportHost.id = 'scheduler-pro-html-template-import'
document.body.appendChild(htmlTemplateImportHost)
createApp(AdminHtmlTemplateImportOverlay).mount(htmlTemplateImportHost)

const secondFactorHost = document.createElement('div')
secondFactorHost.id = 'scheduler-pro-admin-second-factor'
document.body.appendChild(secondFactorHost)
createApp(AdminSecondFactorGate).mount(secondFactorHost)
