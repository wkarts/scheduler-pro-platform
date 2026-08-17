<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { apiDelete, apiGet, apiPost, apiPut, type ApiError } from './api/client'

type SessionState = {
  accessToken: string
  refreshToken: string
  userEmail: string
}

type TenantRow = {
  id: string
  name: string
  slug: string
  status: string
}

type TenantManagementSnapshot = {
  tenant: {
    id: string
    name: string
    slug: string
    status: string
    timezone: string
    primary_hostname?: string | null
    created_at?: string | null
  }
  principal_admin?: {
    id: string
    email: string
    display_name: string
    is_active: boolean
    created_at?: string | null
  } | null
  principal_admin_error?: {
    type: string
    message: string
  } | null
  slug_editable: boolean
  slug_note: string
}

const storageKey = 'scheduler-pro-admin-session'
const isOpen = ref(false)
const authenticated = ref(false)
const loading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const tenants = ref<TenantRow[]>([])
const selectedTenantId = ref('')
const snapshot = ref<TenantManagementSnapshot | null>(null)
const tenantName = ref('')
const tenantTimezone = ref('America/Bahia')
const adminEmail = ref('')
const adminDisplayName = ref('')
const adminPassword = ref('')
let sessionTimer: number | undefined

const selectedTenant = computed(() =>
  tenants.value.find(item => item.id === selectedTenantId.value) ?? null,
)

function session(): SessionState | null {
  const raw = localStorage.getItem(storageKey)
  if (!raw) return null
  try {
    return JSON.parse(raw) as SessionState
  } catch {
    return null
  }
}

function token(): string {
  return session()?.accessToken || ''
}

function describeError(error: unknown, fallback: string): string {
  const value = error as Partial<ApiError>
  if (value?.message && value?.code) return `${value.message} (${value.code})`
  return value?.message || fallback
}

function syncAuthentication(): void {
  authenticated.value = Boolean(token())
  if (!authenticated.value) {
    isOpen.value = false
    snapshot.value = null
  }
}

function applySnapshot(value: TenantManagementSnapshot): void {
  snapshot.value = value
  tenantName.value = value.tenant.name
  tenantTimezone.value = value.tenant.timezone || 'America/Bahia'
  adminEmail.value = value.principal_admin?.email || ''
  adminDisplayName.value = value.principal_admin?.display_name || ''
  adminPassword.value = ''
}

async function loadTenants(): Promise<void> {
  tenants.value = await apiGet<TenantRow[]>('/platform/tenants', token())
  if (!selectedTenantId.value && tenants.value.length) {
    selectedTenantId.value = tenants.value[0].id
  }
}

async function loadSnapshot(): Promise<void> {
  snapshot.value = null
  if (!selectedTenantId.value) return
  const value = await apiGet<TenantManagementSnapshot>(
    `/platform/tenant-management/${selectedTenantId.value}`,
    token(),
  )
  applySnapshot(value)
}

async function openManager(): Promise<void> {
  isOpen.value = true
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    await loadTenants()
    await loadSnapshot()
  } catch (error) {
    errorMessage.value = describeError(error, 'Não foi possível carregar a gestão do tenant.')
  } finally {
    loading.value = false
  }
}

async function selectTenant(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    await loadSnapshot()
  } catch (error) {
    errorMessage.value = describeError(error, 'Falha ao carregar o tenant selecionado.')
  } finally {
    loading.value = false
  }
}

async function saveTenant(): Promise<void> {
  if (!selectedTenantId.value) return
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const value = await apiPut<TenantManagementSnapshot>(
      `/platform/tenant-management/${selectedTenantId.value}`,
      {
        name: tenantName.value.trim(),
        timezone: tenantTimezone.value.trim(),
      },
      token(),
    )
    applySnapshot(value)
    await loadTenants()
    successMessage.value = 'Dados do tenant atualizados.'
  } catch (error) {
    errorMessage.value = describeError(error, 'Falha ao atualizar o tenant.')
  } finally {
    loading.value = false
  }
}

async function savePrincipalAdmin(): Promise<void> {
  if (!selectedTenantId.value) return
  if (adminPassword.value && adminPassword.value.length < 12) {
    errorMessage.value = 'A nova senha deve ter no mínimo 12 caracteres.'
    return
  }
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const payload: Record<string, string> = {
      email: adminEmail.value.trim(),
      display_name: adminDisplayName.value.trim() || 'Administrador',
    }
    if (adminPassword.value) payload.password = adminPassword.value
    const value = await apiPut<TenantManagementSnapshot>(
      `/platform/tenant-management/${selectedTenantId.value}/principal-admin`,
      payload,
      token(),
    )
    applySnapshot(value)
    successMessage.value = adminPassword.value
      ? 'Usuário principal atualizado, senha trocada e sessões antigas revogadas.'
      : 'Usuário principal do tenant atualizado.'
  } catch (error) {
    errorMessage.value = describeError(error, 'Falha ao atualizar o usuário principal.')
  } finally {
    loading.value = false
  }
}

async function lifecycle(action: 'suspend' | 'restore'): Promise<void> {
  if (!selectedTenantId.value || !selectedTenant.value) return
  const label = action === 'suspend' ? 'suspender' : 'restaurar'
  if (!window.confirm(`Deseja ${label} ${selectedTenant.value.name}?`)) return
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    await apiPost(`/platform/tenants/${selectedTenantId.value}/${action}`, {}, token())
    await loadTenants()
    await loadSnapshot()
    successMessage.value = action === 'suspend' ? 'Tenant suspenso.' : 'Tenant restaurado.'
  } catch (error) {
    errorMessage.value = describeError(error, `Falha ao ${label} tenant.`)
  } finally {
    loading.value = false
  }
}

async function logicalDelete(): Promise<void> {
  if (!selectedTenantId.value || !selectedTenant.value) return
  if (!window.confirm(
    `Excluir logicamente ${selectedTenant.value.name}? Os recursos serão preservados e o tenant poderá ser restaurado.`,
  )) return
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    await apiDelete(`/platform/tenants/${selectedTenantId.value}`, token())
    await loadTenants()
    await loadSnapshot()
    successMessage.value = 'Tenant excluído logicamente. Banco, storage e artefatos foram preservados.'
  } catch (error) {
    errorMessage.value = describeError(error, 'Falha ao excluir tenant.')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  syncAuthentication()
  sessionTimer = window.setInterval(syncAuthentication, 800)
})

onUnmounted(() => {
  if (sessionTimer !== undefined) window.clearInterval(sessionTimer)
})
</script>

<template>
  <div v-if="authenticated" class="tenant-manager-root">
    <button class="tenant-manager-trigger" type="button" @click="openManager">
      <span>▤</span>
      <strong>Gerenciar tenant</strong>
    </button>

    <div v-if="isOpen" class="tenant-manager-backdrop" @click.self="isOpen = false">
      <section class="tenant-manager-drawer" role="dialog" aria-modal="true" aria-label="Gerenciar tenant">
        <header>
          <div>
            <span class="tenant-manager-eyebrow">Control Plane</span>
            <h2>Gerenciar tenant</h2>
            <p>Cadastro, usuário principal, senha e ciclo de vida em um único lugar.</p>
          </div>
          <button class="tenant-manager-close" type="button" @click="isOpen = false">×</button>
        </header>

        <div class="tenant-manager-selector">
          <label>Tenant</label>
          <select v-model="selectedTenantId" :disabled="loading" @change="selectTenant">
            <option value="">Selecione</option>
            <option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">
              {{ tenant.name }} — {{ tenant.slug }}
            </option>
          </select>
        </div>

        <p v-if="errorMessage" class="tenant-manager-error">{{ errorMessage }}</p>
        <p v-if="successMessage" class="tenant-manager-success">{{ successMessage }}</p>
        <p v-if="loading" class="tenant-manager-loading">Atualizando dados...</p>

        <template v-if="snapshot">
          <div class="tenant-manager-status">
            <div><span>Status</span><strong>{{ snapshot.tenant.status }}</strong></div>
            <div><span>Domínio</span><strong>{{ snapshot.tenant.primary_hostname || 'Pendente' }}</strong></div>
          </div>

          <form class="tenant-manager-card" @submit.prevent="saveTenant">
            <div class="tenant-manager-title">
              <div><h3>Dados do tenant</h3><p>Edite os dados operacionais sem alterar os identificadores isolados.</p></div>
            </div>
            <label>Nome da empresa</label>
            <input v-model="tenantName" minlength="2" maxlength="160" required />
            <label>Código do tenant</label>
            <input :value="snapshot.tenant.slug" disabled />
            <small>{{ snapshot.slug_note }}</small>
            <label>Fuso horário</label>
            <input v-model="tenantTimezone" maxlength="64" required />
            <button class="tenant-manager-primary" type="submit" :disabled="loading">Salvar dados</button>
          </form>

          <form class="tenant-manager-card" @submit.prevent="savePrincipalAdmin">
            <div class="tenant-manager-title">
              <div><h3>Usuário principal do tenant</h3><p>Conta administrativa gravada no banco isolado deste cliente.</p></div>
            </div>
            <template v-if="snapshot.principal_admin">
              <label>E-mail principal</label>
              <input v-model="adminEmail" type="email" required />
              <label>Nome de exibição</label>
              <input v-model="adminDisplayName" minlength="2" maxlength="160" />
              <label>Nova senha</label>
              <input
                v-model="adminPassword"
                type="password"
                minlength="12"
                maxlength="128"
                autocomplete="new-password"
                placeholder="Deixe vazio para manter a senha atual"
              />
              <small>Ao trocar a senha, todas as sessões anteriores desse usuário são revogadas.</small>
              <button class="tenant-manager-primary" type="submit" :disabled="loading">
                Atualizar usuário principal
              </button>
            </template>
            <div v-else class="tenant-manager-warning">
              <strong>Administrador principal ainda não disponível.</strong>
              <span>{{ snapshot.principal_admin_error?.message || 'Conclua ou repita o provisionamento do tenant.' }}</span>
            </div>
          </form>

          <section class="tenant-manager-card danger-zone">
            <div class="tenant-manager-title"><div><h3>Ciclo de vida</h3><p>A exclusão padrão é lógica e preserva os recursos do cliente.</p></div></div>
            <div class="tenant-manager-actions">
              <button
                v-if="snapshot.tenant.status !== 'SUSPENDED'"
                type="button"
                :disabled="loading"
                @click="lifecycle('suspend')"
              >Suspender</button>
              <button
                v-if="['SUSPENDED', 'DELETED'].includes(snapshot.tenant.status)"
                type="button"
                :disabled="loading"
                @click="lifecycle('restore')"
              >Restaurar</button>
              <button
                v-if="snapshot.tenant.status !== 'DELETED'"
                class="danger"
                type="button"
                :disabled="loading"
                @click="logicalDelete"
              >Excluir tenant</button>
            </div>
          </section>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tenant-manager-root{position:relative;z-index:5000}.tenant-manager-trigger{position:fixed;right:22px;bottom:22px;display:flex;align-items:center;gap:9px;border:1px solid rgba(17,138,245,.45);border-radius:14px;background:#0b132b;color:#fff;padding:12px 16px;box-shadow:0 18px 50px rgba(2,6,23,.28);cursor:pointer;font:inherit}.tenant-manager-trigger span{display:grid;place-items:center;width:27px;height:27px;border-radius:8px;background:linear-gradient(135deg,#118af5,#00c2b8);font-weight:800}.tenant-manager-trigger strong{font-size:13px}.tenant-manager-backdrop{position:fixed;inset:0;background:rgba(2,6,23,.64);backdrop-filter:blur(5px);display:flex;justify-content:flex-end;z-index:5100}.tenant-manager-drawer{width:min(580px,100%);height:100%;overflow:auto;background:#f8fafc;color:#0f172a;padding:24px;box-shadow:-24px 0 80px rgba(2,6,23,.28)}.tenant-manager-drawer>header{display:flex;gap:18px;align-items:flex-start;justify-content:space-between;margin-bottom:20px}.tenant-manager-drawer h2{margin:4px 0 5px;font-size:26px}.tenant-manager-drawer p{margin:0;color:#64748b;font-size:13px;line-height:1.5}.tenant-manager-eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;font-weight:800;color:#118af5}.tenant-manager-close{border:0;background:transparent;font-size:34px;line-height:1;color:#475569;cursor:pointer}.tenant-manager-selector,.tenant-manager-card{display:grid;gap:8px;background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:16px;margin-bottom:14px}.tenant-manager-selector label,.tenant-manager-card label{font-size:12px;font-weight:750;color:#334155}.tenant-manager-selector select,.tenant-manager-card input{width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:10px;background:#fff;color:#0f172a;padding:10px 11px;font:inherit}.tenant-manager-card input:disabled{background:#f1f5f9;color:#64748b}.tenant-manager-card small{font-size:11px;color:#64748b;line-height:1.45}.tenant-manager-title h3{margin:0;font-size:16px}.tenant-manager-title p{margin-top:3px}.tenant-manager-status{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}.tenant-manager-status>div{background:#0b132b;color:#fff;border-radius:14px;padding:13px}.tenant-manager-status span{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#94a3b8}.tenant-manager-status strong{display:block;margin-top:4px;font-size:13px;overflow-wrap:anywhere}.tenant-manager-primary{border:0;border-radius:10px;background:linear-gradient(135deg,#118af5,#00c2b8);color:#fff;padding:11px 14px;font-weight:800;cursor:pointer}.tenant-manager-primary:disabled,.tenant-manager-actions button:disabled{opacity:.55;cursor:wait}.tenant-manager-actions{display:flex;flex-wrap:wrap;gap:8px}.tenant-manager-actions button{border:1px solid #cbd5e1;background:#fff;color:#334155;border-radius:9px;padding:9px 12px;font-weight:700;cursor:pointer}.tenant-manager-actions .danger{border-color:#fecaca;color:#b91c1c;background:#fff7f7}.danger-zone{border-color:#fed7d7}.tenant-manager-error,.tenant-manager-success,.tenant-manager-loading{border-radius:10px;padding:10px 12px;margin:0 0 12px!important;font-size:12px!important}.tenant-manager-error{background:#fef2f2;color:#b91c1c!important;border:1px solid #fecaca}.tenant-manager-success{background:#ecfdf5;color:#047857!important;border:1px solid #a7f3d0}.tenant-manager-loading{background:#eff6ff;color:#1d4ed8!important;border:1px solid #bfdbfe}.tenant-manager-warning{display:grid;gap:5px;border-radius:10px;background:#fff7ed;border:1px solid #fed7aa;padding:12px;color:#9a3412}.tenant-manager-warning span{font-size:12px}@media(max-width:640px){.tenant-manager-trigger{right:14px;bottom:14px}.tenant-manager-drawer{padding:18px}.tenant-manager-status{grid-template-columns:1fr}.tenant-manager-trigger strong{display:none}}
</style>
