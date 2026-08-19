import fs from 'node:fs'
import path from 'node:path'

const appPath = process.argv[2]
if (!appPath) throw new Error('Informe o caminho do app desktop.')
const root = path.resolve(appPath)
const config = JSON.parse(fs.readFileSync(path.join(root, 'src-tauri', 'tauri.conf.json'), 'utf8'))
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))
const appVue = fs.readFileSync(path.join(root, 'src', 'App.vue'), 'utf8')

if (config?.build?.frontendDist !== '../dist') {
  throw new Error('build.frontendDist deve ser ../dist para empacotar o launcher local.')
}
if (typeof config?.build?.beforeBuildCommand !== 'string' || !config.build.beforeBuildCommand.includes('build')) {
  throw new Error('beforeBuildCommand deve compilar o launcher local.')
}
if (typeof config?.build?.beforeDevCommand !== 'string' || !config.build.beforeDevCommand.includes('dev')) {
  throw new Error('beforeDevCommand deve iniciar o Vite local.')
}
if (typeof config?.build?.devUrl !== 'string' || !/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(config.build.devUrl)) {
  throw new Error('build.devUrl deve apontar para o servidor Vite local.')
}
if (config?.app?.windows?.some((window) => typeof window?.url === 'string' && /^https?:/.test(window.url))) {
  throw new Error('A URL remota não deve ser fixada no tauri.conf; o binário é universal e pergunta a instância no primeiro uso.')
}
if (typeof pkg?.scripts?.build !== 'string' || !pkg.scripts.build.includes('vite build')) {
  throw new Error('package.json precisa gerar dist com vite build.')
}
for (const required of ['index.html', 'src/main.ts', 'src/App.vue', 'vite.config.ts', 'tsconfig.json']) {
  if (!fs.existsSync(path.join(root, required))) throw new Error(`Launcher desktop ausente: ${required}`)
}
if (!appVue.includes('window.location.replace')) {
  throw new Error('Desktop deve abrir a WebApp configurada, sem manter uma interface de negócio duplicada no binário.')
}
if (!appVue.includes('instance_url')) {
  throw new Error('Desktop deve persistir a URL universal configurada no primeiro acesso.')
}
if (/type\s+(ViewKey|ModuleKey)\s*=/.test(appVue) || /appointments\.value|customers\.value|buildJobs\.value/.test(appVue)) {
  throw new Error('Desktop não deve duplicar módulos, agenda ou regras da WebApp.')
}
console.log(`desktop-web-shell-ok ${root}`)
