import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { installTenantExtensionNavigationBridge } from './tenant-extension-bridge'
import './styles.css'
import './operational.css'
import './tenant-console.css'
import './tenant-dashboard-polish.css'
import './branding.css'
import './tenant-dashboard.css'
import './tenant-menu-fix.css'
import './pwa'

installTenantExtensionNavigationBridge()
createApp(App).use(createPinia()).mount('#app')
