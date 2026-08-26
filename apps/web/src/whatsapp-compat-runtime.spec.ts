import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const runtimeSource = readFileSync(new URL('./whatsapp-compat-runtime.ts', import.meta.url), 'utf8')
const mainSource = readFileSync(new URL('./main.ts', import.meta.url), 'utf8')

describe('compatibilidade WhatsApp do tenant', () => {
  it('mantém o painel histórico no contrato de status compatível sem afetar o centro novo', () => {
    expect(runtimeSource).toContain("const STATUS_PATH = '/api/v1/integrations/whatsapp/status'")
    expect(runtimeSource).toContain("const LEGACY_STATUS_PATH = '/api/v1/integrations/whatsapp/status/legacy'")
    expect(runtimeSource).toContain('hasExplicitAuthorization(init?.headers)')
  })

  it('mantém a nomenclatura pública neutra sem trocar o provider interno', () => {
    expect(runtimeSource).toContain(".replace(/ARGWS\\s+WhatsApp\\s+API/gi, 'WhatsApp')")
    expect(runtimeSource).toContain(".replace(/Evolution\\s+API/gi, 'WhatsApp')")
  })

  it('instala a ponte depois do fetch autenticado do tenant', () => {
    const auth = mainSource.indexOf('installTenantAuthFetch()')
    const compat = mainSource.indexOf('installWhatsAppCompatibilityRuntime()')
    expect(auth).toBeGreaterThan(-1)
    expect(compat).toBeGreaterThan(auth)
  })
})
