import { createApp } from 'vue'
import App from './App.vue'
import { prepareMobileRuntimeInstance } from './runtime-instance'
import './styles.css'
import './operational.css'
import './branding.css'

async function bootstrap(): Promise<void> {
  await prepareMobileRuntimeInstance()
  createApp(App).mount('#app')
}

void bootstrap()
