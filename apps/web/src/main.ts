import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './styles.css'
import './operational.css'
import './tenant-console.css'
import './branding.css'
import './tenant-dashboard.css'
import './pwa'

createApp(App).use(createPinia()).mount('#app')
