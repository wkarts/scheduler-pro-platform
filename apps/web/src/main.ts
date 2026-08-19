import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { installTenantAuthFetch } from './tenant-auth-fetch'
import { installTenantExtensionNavigationBridge } from './tenant-extension-bridge'
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
import './pwa'

installTenantAuthFetch()
installTenantExtensionNavigationBridge()
installTenantMobileEnhancements()
createApp(App).use(createPinia()).mount('#app')
