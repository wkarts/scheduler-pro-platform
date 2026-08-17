import fs from 'node:fs'
import path from 'node:path'

const appPath = process.argv[2]
if (!appPath) throw new Error('Informe o caminho do app desktop.')
const root = path.resolve(appPath)
const config = JSON.parse(fs.readFileSync(path.join(root, 'src-tauri', 'tauri.conf.json'), 'utf8'))
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))

if (config?.build?.frontendDist !== '../dist') {
  throw new Error('build.frontendDist deve ser ../dist para empacotar o frontend local.')
}
if (typeof config?.build?.beforeBuildCommand !== 'string' || !config.build.beforeBuildCommand.includes('build')) {
  throw new Error('beforeBuildCommand deve compilar o frontend local.')
}
if (typeof config?.build?.beforeDevCommand !== 'string' || !config.build.beforeDevCommand.includes('dev')) {
  throw new Error('beforeDevCommand deve iniciar o Vite local.')
}
if (typeof config?.build?.devUrl !== 'string' || !/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(config.build.devUrl)) {
  throw new Error('build.devUrl deve apontar para o servidor Vite local.')
}
if (config?.app?.windows?.some((window) => typeof window?.url === 'string' && /^https?:/.test(window.url))) {
  throw new Error('A janela desktop não pode substituir o bundle local por URL remota.')
}
if (typeof pkg?.scripts?.build !== 'string' || !pkg.scripts.build.includes('vite build')) {
  throw new Error('package.json precisa gerar dist com vite build.')
}
for (const required of ['index.html', 'src/main.ts', 'src/App.vue', 'vite.config.ts', 'tsconfig.json']) {
  if (!fs.existsSync(path.join(root, required))) throw new Error(`Frontend desktop ausente: ${required}`)
}
console.log(`desktop-local-ok ${root}`)
