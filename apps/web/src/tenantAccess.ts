import { reactive } from 'vue'
export const tenantAccess = reactive({ loaded: false, permissions: [] as string[], capabilities: [] as string[] })
export const canAccess = (permission: string) => tenantAccess.loaded && tenantAccess.permissions.includes(permission)
export const hasFeature = (feature: string) => tenantAccess.capabilities.includes(feature)
export function setTenantAccess(permissions: string[], capabilities: string[]): void {
  tenantAccess.permissions = permissions; tenantAccess.capabilities = capabilities; tenantAccess.loaded = true
}
