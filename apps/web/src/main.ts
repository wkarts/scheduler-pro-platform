import IntegrationServicesLauncher from '../../../packages/integration-services/IntegrationServicesLauncher.vue'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { installTenantAuthFetch } from './tenant-auth-fetch'
import { installTenantFrontendTelemetry } from './tenant-frontend-telemetry'
import { installTenantMobileEnhancements } from './tenant-mobile-enhancements'
import './styles.css'
import './operational.css'
import './tenant-console.css'
import './tenant-dashboard-polish.css'
import './branding.css'
import './tenant-dashboard.css'
import './tenant-menu-fix.css'
import './tenant-mobile-native.css'
import './tenant-mobile-picker.css'
import './tenant-shell-contract.css'
import './tenant-overlay-layering.css'
import './scrollbars.css'
import './pwa'

installTenantAuthFetch()
installTenantMobileEnhancements()
installTenantFrontendTelemetry()
createApp(App).use(createPinia()).mount('#app')

// Additive service integration center; keeps the existing tenant/admin shell intact.
const integrationServicesHost = document.createElement('div')
integrationServicesHost.id = 'scheduler-pro-integration-services'
document.body.appendChild(integrationServicesHost)
createApp(IntegrationServicesLauncher, { platform: false }).mount(integrationServicesHost)
