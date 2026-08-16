import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './AdminControlPlane.vue'
import './styles.css'
import './operational.css'
import './hubfiscal-admin.css'
import './enterprise.css'
import './pwa'

createApp(App).use(createPinia()).mount('#app')
