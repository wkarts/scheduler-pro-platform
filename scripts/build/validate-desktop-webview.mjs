import fs from 'node:fs'
import path from 'node:path'

const appPath = process.argv[2]
if (!appPath) throw new Error('Informe o caminho do app desktop.')
const configPath = path.resolve(appPath, 'src-tauri', 'tauri.conf.json')
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
const frontendDist = config?.build?.frontendDist
const windowUrl = config?.app?.windows?.[0]?.url

for (const [name, value] of [['build.frontendDist', frontendDist], ['app.windows[0].url', windowUrl]]) {
  if (typeof value !== 'string' || !value.startsWith('https://')) {
    throw new Error(`${name} deve apontar para uma URL HTTPS remota.`)
  }
}
if (frontendDist.replace(/\/$/, '') !== windowUrl.replace(/\/$/, '')) {
  throw new Error('frontendDist e URL da janela devem apontar para a mesma aplicação web.')
}
if (config?.build?.beforeBuildCommand || config?.build?.beforeDevCommand) {
  throw new Error('Desktop remoto não deve buildar ou iniciar frontend local.')
}
console.log(`desktop-remote-ok ${windowUrl}`)
