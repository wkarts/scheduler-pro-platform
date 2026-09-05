<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef } from 'vue'

type Scope = { key: string; label: string }
type Operation = { method: string; path: string; scope: string; idempotency_required: boolean }
type Catalog = { scope: string; api_enabled: boolean; webhooks_enabled: boolean; webhook_management_allowed: boolean; scopes: Scope[]; events: string[]; operations: Operation[]; replay_hours: number; retention_days: number; excluded: string[] }
type Token = { id: string; owner_id: string; name: string; prefix: string; scopes: string[]; expires_at: string; revoked_at: string | null; last_used_at: string | null; rate_limit: number }
type Endpoint = { id: string; name: string; url: string; events: string[]; active: boolean; has_authorization: boolean }
type Delivery = { id: string; name: string; event_id: string; event_type: string; state: string; attempts: number; http_status: number | null; last_error: string | null; created_at: string }
type ApiRequest = { id: string; method: string; path: string; state: string; response_status: number | null; created_at: string }
type Attempt = { attempt: number; http_status: number | null; error: string | null; started_at: string; finished_at: string | null }
type Tab = 'tokens' | 'webhooks' | 'deliveries' | 'requests' | 'catalog'
const props = defineProps<{ platform?: boolean }>()
const base = computed(() => props.platform ? '/api/v1/platform/integrations/services' : '/api/v1/integrations/services')
const target = shallowRef<HTMLElement | null>(null)
const dialog = ref<HTMLDialogElement | null>(null)
const opened = ref(false)
const tab = ref<Tab>('tokens')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const catalog = ref<Catalog | null>(null)
const tokens = ref<Token[]>([])
const endpoints = ref<Endpoint[]>([])
const deliveries = ref<Delivery[]>([])
const requests = ref<ApiRequest[]>([])
const secret = ref('')
const secretTitle = ref('')
const filter = ref('')
const offset = ref(0)
const attempts = ref<Attempt[] | null>(null)
const confirmation = shallowRef<{ message: string; run: () => Promise<void> } | null>(null)
const tokenForm = ref({ name: '', scopes: [] as string[], expires_in_days: 90, rate_limit: 120 })
const webhookForm = ref({ name: '', url: '', events: [] as string[], active: true, authorization_token: '', clear_authorization: false })
const editing = ref<string | null>(null)
const reviewing = ref<ApiRequest | null>(null)
const reviewNote = ref('')
let panelEpoch = 0
let panelIdentity = ""
let refreshObserver: ReturnType<typeof setInterval> | undefined
let observer: MutationObserver | undefined
let previousFocus: HTMLElement | null = null

function bearer(): string {
  try {
    if (props.platform) return String(JSON.parse(localStorage.getItem('scheduler-pro-admin-session') || '{}').accessToken || '')
    return localStorage.getItem('scheduler_pro_access_token') || ''
  } catch { return '' }
}
function sessionIdentity(): string {
  const token = bearer()
  if (!token) return ''
  try {
    const raw = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const payload = JSON.parse(atob(raw.padEnd(Math.ceil(raw.length / 4) * 4, '=')))
    return `${payload.user_type}:${payload.tenant_id || ''}:${payload.sub}:${payload.sid}`
  } catch { return token }
}
function syncHost(): void {
  target.value = bearer() ? document.querySelector<HTMLElement>('.sidebar .nav-list') : null
  if (opened.value && (!target.value || panelIdentity !== sessionIdentity())) close()
}
function close(): void {
  panelEpoch += 1
  reviewing.value = null
  reviewNote.value = ''
  dialog.value?.close()
  opened.value = false
  secret.value = ''
  webhookForm.value.authorization_token = ''
  confirmation.value = null
  previousFocus?.focus()
}
async function open(next: Tab): Promise<void> {
  panelIdentity = sessionIdentity()
  tab.value = next
  offset.value = 0
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  tokens.value = []; endpoints.value = []; deliveries.value = []; requests.value = []
  secret.value = ''; error.value = ''; notice.value = ''
  opened.value = true
  await nextTick()
  if (!dialog.value?.open) dialog.value?.showModal()
  await reload()
}

// Persist only a request digest and random key. Never persist tokens, payloads or signing secrets.
async function requestKey(path: string, method: string, body: string): Promise<{ storage: string; key: string }> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${sessionIdentity()}|${base.value}|${path}|${method}|${body}`))
  const hash = Array.from(new Uint8Array(digest), v => v.toString(16).padStart(2, '0')).join('')
  const storage = `scheduler-integration-request:${props.platform ? 'platform' : 'tenant'}:${hash}`
  let key = sessionStorage.getItem(storage)
  if (!key) { key = crypto.randomUUID(); sessionStorage.setItem(storage, key) }
  return { storage, key }
}
async function api<T>(path: string, method = 'GET', payload?: unknown): Promise<T> {
  const epoch = panelEpoch
  const session = sessionIdentity()
  const body = payload === undefined ? undefined : JSON.stringify(payload)
  const headers: Record<string, string> = { Authorization: `Bearer ${bearer()}`, Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const mutation = !['GET', 'HEAD'].includes(method)
  const key = mutation ? await requestKey(path, method, body || '') : null
  if (key) headers['Idempotency-Key'] = key.key
  const response = await fetch(base.value + path, { method, headers, body, cache: 'no-store' })
  const result = await response.json()
  if (epoch !== panelEpoch || session !== sessionIdentity()) {
    throw new Error('A sessão ou o painel mudou. Consulte a operação antes de repetir.')
  }
  if (!response.ok) {
    const message = result.error?.message || `Falha HTTP ${response.status}`
    const identifier = response.headers.get('x-idempotency-request-id') || result.error?.details?.request_id
    throw new Error(identifier ? `${message} Operação: ${identifier}` : message)
  }
  if (key) sessionStorage.removeItem(key.storage)
  return result.data as T
}
async function reload(): Promise<void> {
  loading.value = true; error.value = ''; attempts.value = null
  try {
    catalog.value = await api<Catalog>('/catalog')
    if (['webhooks', 'deliveries'].includes(tab.value) && !catalog.value.webhook_management_allowed) {
      throw new Error('Webhooks globais exigem administração global. Seus tokens de API continuam independentes.')
    }
    if (!tokenForm.value.scopes.length) tokenForm.value.scopes = [props.platform ? 'dashboard.read' : 'customers.read']
    if (tab.value === 'tokens') tokens.value = await api<Token[]>('/tokens')
    if (tab.value === 'webhooks') endpoints.value = await api<Endpoint[]>('/webhooks')
    if (tab.value === 'deliveries') deliveries.value = await api<Delivery[]>(`/deliveries?offset=${offset.value}`)
    if (tab.value === 'requests') requests.value = await api<ApiRequest[]>(`/requests?offset=${offset.value}`)
  } catch (failure) { error.value = failure instanceof Error ? failure.message : 'Não foi possível carregar as integrações.' }
  finally { loading.value = false }
}
async function switchTab(next: Tab): Promise<void> { tab.value = next; offset.value = 0; await reload() }
async function mutate(action: () => Promise<void>): Promise<void> {
  if (saving.value) return
  saving.value = true; error.value = ''; notice.value = ''
  try { await action(); await reload() }
  catch (failure) { error.value = failure instanceof Error ? failure.message : 'Operação não concluída.' }
  finally { saving.value = false }
}
async function createToken(): Promise<void> {
  await mutate(async () => {
    const response = await api<{ token: string }>('/tokens', 'POST', tokenForm.value)
    secretTitle.value = 'Token de API — guarde em um local seguro'; secret.value = response.token
    tokenForm.value.name = ''; notice.value = 'Token criado. A credencial não será exibida nas listagens.'
  })
}
function ask(message: string, run: () => Promise<void>): void { confirmation.value = { message, run } }
async function acceptConfirmation(): Promise<void> {
  const action = confirmation.value?.run; confirmation.value = null
  if (action) await mutate(action)
}
function rotateToken(item: Token): void {
  ask(`Rotacionar ${item.name}? A credencial anterior deixará de funcionar imediatamente.`, async () => {
    const response = await api<{ token: string }>(`/tokens/${item.id}/rotate`, 'POST', {})
    secretTitle.value = 'Novo token — atualize a integração'; secret.value = response.token
  })
}
function revokeToken(item: Token): void {
  ask(`Revogar o token ${item.name}? Somente esta credencial será bloqueada.`, async () => {
    await api(`/tokens/${item.id}`, 'DELETE'); notice.value = 'Token revogado.'
  })
}
function editWebhook(item: Endpoint): void {
  editing.value = item.id
  webhookForm.value = { name: item.name, url: item.url, events: [...item.events], active: item.active, authorization_token: '', clear_authorization: false }
}
function resetWebhook(): void {
  editing.value = null
  webhookForm.value = { name: '', url: '', events: [], active: true, authorization_token: '', clear_authorization: false }
}
async function saveWebhook(): Promise<void> {
  await mutate(async () => {
    const response = await api<{ signing_secret?: string }>(editing.value ? `/webhooks/${editing.value}` : '/webhooks', editing.value ? 'PUT' : 'POST', webhookForm.value)
    if (response.signing_secret) { secretTitle.value = 'Segredo de assinatura do webhook'; secret.value = response.signing_secret }
    resetWebhook(); notice.value = 'Destino salvo. A entrega ocorre em segundo plano pelo worker de webhooks.'
  })
}
function rotateWebhook(item: Endpoint): void {
  ask(`Rotacionar a assinatura de ${item.name}? Atualize o receptor; a chave anterior não será mais utilizada.`, async () => {
    const response = await api<{ signing_secret: string }>(`/webhooks/${item.id}/rotate-secret`, 'POST', {})
    secretTitle.value = 'Novo segredo de assinatura'; secret.value = response.signing_secret
  })
}
function removeWebhook(item: Endpoint): void {
  ask(`Remover ${item.name}? Novos eventos não serão enviados e o histórico será preservado pela retenção.`, async () => { await api(`/webhooks/${item.id}`, 'DELETE') })
}
async function testWebhook(item: Endpoint): Promise<void> {
  await mutate(async () => {
    const result = await api<{ delivery_id: string }>(`/webhooks/${item.id}/test`, 'POST', {})
    notice.value = `Teste enfileirado. Entrega: ${result.delivery_id}`
  })
}
async function inspectDelivery(item: Delivery): Promise<void> {
  try { attempts.value = await api<Attempt[]>(`/deliveries/${item.id}/attempts`) }
  catch (failure) { error.value = String(failure) }
}
function retryDelivery(item: Delivery): void {
  ask('Reenviar esta entrega? O identificador será preservado para deduplicação no receptor.', async () => {
    await api(`/deliveries/${item.id}/retry`, 'POST', {}); notice.value = 'Entrega reenfileirada.'
  })
}
async function copySecret(): Promise<void> {
  try { await navigator.clipboard.writeText(secret.value); notice.value = 'Credencial copiada.' }
  catch { error.value = 'Não foi possível copiar. Selecione e copie o texto da credencial.' }
}
async function downloadOpenAPI(): Promise<void> {
  try {
    const response = await fetch(base.value + '/openapi', { headers: { Authorization: `Bearer ${bearer()}` }, cache: 'no-store' })
    if (!response.ok) throw new Error('Não foi possível exportar o OpenAPI.')
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a'); link.href = url; link.download = `scheduler-${props.platform ? 'platform' : 'tenant'}-openapi.json`; link.click(); URL.revokeObjectURL(url)
  } catch (failure) { error.value = String(failure) }
}
async function resolveOutcome(): Promise<void> {
  const request = reviewing.value
  if (!request || reviewNote.value.trim().length < 10) return
  await mutate(async () => {
    await api(`/requests/${request.id}/resolve-outcome`, 'POST', { note: reviewNote.value.trim(), reviewed: true })
    reviewing.value = null; reviewNote.value = ''
    notice.value = 'Conferência registrada. A chave original continua bloqueada para nova execução.'
  })
}
function date(value: string | null): string { return value ? new Date(value).toLocaleString('pt-BR') : '—' }
const operations = computed(() => (catalog.value?.operations || []).filter(item => `${item.method} ${item.path} ${item.scope}`.toLowerCase().includes(filter.value.toLowerCase())))
const curlExample = computed(() => `curl '${window.location.origin}/api/v1/${props.platform ? 'platform/tenants' : 'customers'}' \\\n  -H 'Authorization: Bearer SEU_TOKEN'`)
const tabs: Array<{ key: Tab; title: string }> = [{ key: 'tokens', title: 'API Services' }, { key: 'webhooks', title: 'Webhook Services' }, { key: 'deliveries', title: 'Entregas' }, { key: 'requests', title: 'Operações' }, { key: 'catalog', title: 'Documentação' }]
onMounted(() => { syncHost(); refreshObserver = setInterval(syncHost, 1000); observer = new MutationObserver(syncHost); observer.observe(document.body, { childList: true, subtree: true }); window.addEventListener('storage', syncHost) })
onUnmounted(() => { if (refreshObserver) clearInterval(refreshObserver); observer?.disconnect(); window.removeEventListener('storage', syncHost); close() })
</script>

<template>
  <Teleport v-if="target" :to="target">
    <button class="nav-item integration-nav" type="button" title="API Services" @click="open('tokens')"><span aria-hidden="true">⌘</span><span class="integration-nav-label">API Services</span></button>
    <button class="nav-item integration-nav" type="button" title="Webhook Services" @click="open('webhooks')"><span aria-hidden="true">⇄</span><span class="integration-nav-label">Webhook Services</span></button>
  </Teleport>
  <dialog ref="dialog" class="integration-dialog" aria-labelledby="integration-title" @cancel.prevent="close" @close="opened = false">
    <div v-if="opened" class="integration-center">
      <header class="integration-header"><div><small>{{ platform ? 'CONTROL PLANE' : 'EMPRESA' }} · INTEGRAÇÕES</small><h2 id="integration-title">API Services &amp; Webhook Services</h2><p>Credenciais individuais, operações rastreáveis e eventos assinados.</p></div><button type="button" class="integration-button" aria-label="Fechar integrações" @click="close">Fechar ×</button></header>
      <nav class="integration-tabs" aria-label="Áreas de integração"><button v-for="item in tabs" :key="item.key" type="button" :class="{ selected: tab === item.key }" :disabled="loading || saving" @click="switchTab(item.key)">{{ item.title }}</button></nav>
      <div class="integration-body">
        <div v-if="error" role="alert" class="integration-alert error">{{ error }}</div><div v-if="notice" role="status" class="integration-alert">{{ notice }}</div>
        <section v-if="secret" class="integration-secret"><strong>{{ secretTitle }}</strong><p>Não envie esta credencial por e-mail ou WhatsApp. Ela não será salva neste navegador.</p><textarea :value="secret" readonly rows="3" aria-label="Credencial gerada"></textarea><div class="integration-actions"><button type="button" class="integration-button" @click="copySecret">Copiar</button><button type="button" class="integration-button" @click="secret = ''">Já guardei; ocultar</button></div></section>
        <section v-if="confirmation" class="integration-confirm" role="alertdialog" aria-label="Confirmar ação"><p>{{ confirmation.message }}</p><div class="integration-actions"><button type="button" class="integration-button primary" @click="acceptConfirmation">Confirmar</button><button type="button" class="integration-button" @click="confirmation = null">Cancelar</button></div></section>
        <div class="integration-toolbar"><span>{{ loading ? 'Atualizando…' : `${platform ? 'Ambiente administrativo' : 'Ambiente exclusivo da empresa'}` }}</span><button type="button" class="integration-button" :disabled="loading || saving" @click="reload">Atualizar</button></div>
        <template v-if="tab === 'tokens'">
          <form class="integration-card" @submit.prevent="createToken"><h3>Novo token individual</h3><p>O token nunca terá mais permissões que seu usuário. A administração de tokens exige sessão interativa.</p><div class="integration-grid"><label>Nome da integração<input v-model="tokenForm.name" required minlength="2" maxlength="100" placeholder="ERP / CRM / automação"></label><label>Validade em dias<input v-model.number="tokenForm.expires_in_days" type="number" min="1" max="365" required></label><label>Requisições por minuto<input v-model.number="tokenForm.rate_limit" type="number" min="1" max="1000" required></label></div><details open><summary>Escopos permitidos</summary><div class="integration-choices"><label v-for="scope in catalog?.scopes" :key="scope.key"><input v-model="tokenForm.scopes" type="checkbox" :value="scope.key">{{ scope.label }}</label></div></details><button class="integration-button primary" type="submit" :disabled="saving || !tokenForm.scopes.length">Gerar token</button></form>
          <div class="integration-table"><table><thead><tr><th>Integração</th><th>Validade / uso</th><th>Limite</th><th>Ações</th></tr></thead><tbody><tr v-for="item in tokens" :key="item.id"><td><strong>{{ item.name }}</strong><code>{{ item.prefix }}…</code><small>{{ item.scopes.join(', ') }}</small></td><td>{{ date(item.expires_at) }}<small>Último uso: {{ date(item.last_used_at) }}</small><b v-if="item.revoked_at">Revogado</b></td><td>{{ item.rate_limit }}/min</td><td><div class="integration-actions"><button class="integration-button" :disabled="saving || Boolean(item.revoked_at)" @click="rotateToken(item)">Rotacionar</button><button class="integration-button" :disabled="saving || Boolean(item.revoked_at)" @click="revokeToken(item)">Revogar</button></div></td></tr><tr v-if="!tokens.length"><td colspan="4">Nenhum token cadastrado.</td></tr></tbody></table></div>
        </template>
        <template v-if="tab === 'webhooks'">
          <div v-if="catalog && !catalog.webhooks_enabled" class="integration-alert">Entregas desativadas na configuração deste serviço.</div>
          <form v-if="catalog?.webhook_management_allowed" class="integration-card" @submit.prevent="saveWebhook"><h3>{{ editing ? 'Editar destino' : 'Novo destino de eventos' }}</h3><p>Opcional. Utilize para sincronizar alterações com sistemas externos sem consultas contínuas.</p><div class="integration-grid"><label>Nome<input v-model="webhookForm.name" required minlength="2" maxlength="100"></label><label class="wide">URL HTTPS pública<input v-model="webhookForm.url" type="url" required placeholder="https://sua-integracao.exemplo/webhooks/scheduler"></label></div><label>Bearer adicional do receptor (opcional)<input v-model="webhookForm.authorization_token" type="password" autocomplete="new-password" placeholder="Vazio preserva a credencial na edição"></label><label v-if="editing" class="integration-inline"><input v-model="webhookForm.clear_authorization" type="checkbox">Remover Bearer adicional</label><details open><summary>Eventos assinados</summary><div class="integration-choices"><label><input v-model="webhookForm.events" type="checkbox" value="*">Todos os eventos deste ambiente</label><label v-for="event in catalog?.events" :key="event"><input v-model="webhookForm.events" type="checkbox" :value="event">{{ event }}</label></div></details><label class="integration-inline"><input v-model="webhookForm.active" type="checkbox">Destino ativo</label><div class="integration-actions"><button class="integration-button primary" type="submit" :disabled="saving || !webhookForm.events.length">{{ editing ? 'Salvar destino' : 'Criar destino' }}</button><button v-if="editing" type="button" class="integration-button" @click="resetWebhook">Cancelar edição</button></div></form>
          <article v-for="item in endpoints" :key="item.id" class="integration-card"><h3>{{ item.name }} <small>{{ item.active ? 'Ativo' : 'Pausado' }}</small></h3><code>{{ item.url }}</code><p>{{ item.events.join(', ') }}</p><div class="integration-actions"><button class="integration-button" :disabled="saving" @click="editWebhook(item)">Editar</button><button class="integration-button" :disabled="saving" @click="mutate(async () => { await api(`/webhooks/${item.id}/status`, 'PATCH', { active: !item.active }) })">{{ item.active ? 'Pausar' : 'Ativar' }}</button><button class="integration-button" :disabled="saving || !item.active" @click="testWebhook(item)">Enviar teste</button><button class="integration-button" :disabled="saving" @click="rotateWebhook(item)">Rotacionar segredo</button><button class="integration-button" :disabled="saving" @click="removeWebhook(item)">Remover</button></div></article>
        </template>
        <template v-if="tab === 'deliveries'">
          <p>Falhas temporárias têm novas tentativas com intervalo progressivo. O receptor deve deduplicar pelo identificador da entrega.</p><div class="integration-table"><table><thead><tr><th>Destino / evento</th><th>Situação</th><th>Tentativas</th><th>Ações</th></tr></thead><tbody><tr v-for="item in deliveries" :key="item.id"><td>{{ item.name }}<code>{{ item.event_type }}</code><small>{{ item.id }}</small></td><td>{{ item.state }}<small>HTTP {{ item.http_status || '—' }} · {{ item.last_error || 'Sem erro registrado' }}</small></td><td>{{ item.attempts }}</td><td><div class="integration-actions"><button class="integration-button" @click="inspectDelivery(item)">Histórico</button><button v-if="['failed', 'cancelled'].includes(item.state)" class="integration-button" :disabled="saving" @click="retryDelivery(item)">Reenviar</button></div></td></tr><tr v-if="!deliveries.length"><td colspan="4">Nenhuma entrega nesta página.</td></tr></tbody></table></div><section v-if="attempts" class="integration-card"><h3>Histórico de tentativas</h3><p v-for="item in attempts" :key="item.attempt">#{{ item.attempt }} · {{ date(item.started_at) }} · HTTP {{ item.http_status || '—' }} · {{ item.error || (item.finished_at ? 'Concluída' : 'Iniciada / sem conclusão registrada') }}</p></section>
        </template>
        <template v-if="tab === 'requests'"><section v-if="reviewing" class="integration-card"><h3>Conferência manual</h3><code>{{ reviewing.id }}</code><p>Confira no recurso original se a gravação aconteceu. Este registro não executa, desfaz ou repete a operação.</p><label>Resultado da conferência<textarea v-model="reviewNote" rows="3" minlength="10" maxlength="500" placeholder="Descreva o que foi verificado, sem dados sensíveis."></textarea></label><div class="integration-actions"><button class="integration-button primary" :disabled="saving || reviewNote.trim().length &lt; 10" @click="resolveOutcome">Conferi o resultado; registrar</button><button class="integration-button" @click="reviewing = null">Cancelar</button></div></section><p>Operações com resultado incerto não são executadas novamente automaticamente. Confira o recurso afetado antes de iniciar outra operação.</p><div class="integration-table"><table><thead><tr><th>Operação</th><th>Estado</th><th>Resposta</th><th>Recebida</th></tr></thead><tbody><tr v-for="item in requests" :key="item.id"><td><code>{{ item.method }} {{ item.path }}</code><small>{{ item.id }}</small></td><td>{{ item.state }}<button v-if="['unknown', 'processing'].includes(item.state)" class="integration-button" :disabled="saving" @click="reviewing = item; reviewNote = ''">Registrar conferência</button></td><td>{{ item.response_status || '—' }}</td><td>{{ date(item.created_at) }}</td></tr><tr v-if="!requests.length"><td colspan="4">Nenhuma operação nesta página.</td></tr></tbody></table></div></template>
        <div v-if="tab === 'requests' || tab === 'deliveries'" class="integration-actions"><button class="integration-button" :disabled="offset === 0 || loading" @click="offset = Math.max(0, offset - 50); reload()">Anterior</button><span>Página {{ offset / 50 + 1 }}</span><button class="integration-button" :disabled="loading || (tab === 'requests' ? requests.length : deliveries.length) < 50" @click="offset += 50; reload()">Próxima</button></div>
        <template v-if="tab === 'catalog'"><section class="integration-card"><h3>Contrato para integração</h3><p>Autenticação: <code>Authorization: Bearer SEU_TOKEN</code>. Em POST, PUT, PATCH e DELETE, envie <code>Idempotency-Key</code> exclusivo por operação e reutilize a mesma chave em reenvios.</p><p>Replay por {{ catalog?.replay_hours }} horas. Chaves concluídas permanecem bloqueadas contra nova execução por {{ catalog?.retention_days }} dias; resultados incertos não são liberados automaticamente.</p><pre>{{ curlExample }}</pre><button class="integration-button primary" @click="downloadOpenAPI">Exportar OpenAPI</button><p>Exceções interativas: {{ catalog?.excluded.join('; ') }}.</p><p>Webhooks usam <code>X-Scheduler-Signature</code> (HMAC-SHA256), timestamp e identificador de entrega. Consulte o guia do repositório para validação e inbox idempotente.</p></section><label>Filtrar operações<input v-model="filter" type="search" placeholder="agendamento, customers, GET…"></label><div class="integration-table"><table><thead><tr><th>Método / caminho</th><th>Escopo</th><th>Idempotência</th></tr></thead><tbody><tr v-for="operation in operations" :key="operation.method + operation.path"><td><code>{{ operation.method }} {{ operation.path }}</code></td><td>{{ operation.scope }}</td><td>{{ operation.idempotency_required ? 'Obrigatória' : 'Consulta' }}</td></tr></tbody></table></div></template>
      </div>
    </div>
  </dialog>
</template>

<style scoped>
.integration-nav>span:first-child{width:19px;text-align:center;flex:0 0 19px;font-size:20px}:global(.collapsed:not(.mobileOpen)) .integration-nav-label{display:none}
.integration-dialog{width:min(1200px,96vw);max-height:94dvh;padding:0;border:1px solid #dfe7f1;border-radius:16px;color:#172b48;background:#f4f7fb;box-shadow:0 24px 80px #10254840;overflow:auto}.integration-dialog::backdrop{background:#10254888}.integration-header{padding:24px;display:flex;gap:20px;justify-content:space-between;align-items:flex-start;background:#fff;border-bottom:1px solid #dfe7f1}.integration-header small{color:var(--blue,#2563eb);font-size:11px;letter-spacing:.1em;font-weight:800}.integration-header h2{font-size:24px;margin:7px 0}.integration-header p,.integration-card p{color:#65758d;font-size:13px;line-height:1.6}.integration-tabs{display:flex;gap:5px;padding:12px 24px;overflow:auto;background:#fff;position:sticky;top:0;z-index:1;border-bottom:1px solid #dfe7f1}.integration-tabs button{white-space:nowrap;border:0;background:transparent;color:#52657e;padding:10px 14px;border-radius:8px;font-weight:700}.integration-tabs .selected{background:#eaf1ff;color:var(--blue,#2563eb)}.integration-body{padding:24px;display:grid;gap:18px}.integration-toolbar,.integration-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.integration-toolbar{justify-content:space-between;color:#65758d;font-size:12px}.integration-button{border:1px solid #cfdbea;background:#fff;color:#233b5c;padding:9px 13px;border-radius:9px;font-size:12px;font-weight:700;min-height:38px;cursor:pointer}.integration-button.primary{background:var(--blue,#2563eb);color:#fff;border-color:var(--blue,#2563eb)}.integration-button:disabled{opacity:.45;cursor:not-allowed}.integration-card,.integration-secret,.integration-confirm{padding:22px;border:1px solid #dfe7f1;border-radius:12px;background:#fff;display:grid;gap:14px}.integration-card h3{margin:0;font-size:17px}.integration-card h3 small{font-size:12px;color:#65758d}.integration-card p{margin:0}.integration-center label{display:grid;gap:7px;font-size:12px;font-weight:700;color:#415773}.integration-center input:not([type=checkbox]),.integration-center textarea{width:100%;border:1px solid #cfdbea;border-radius:8px;padding:11px;background:#fff;color:#172b48;font:inherit}.integration-center input:focus,.integration-center textarea:focus{outline:2px solid #93b9ff;outline-offset:1px}.integration-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px}.integration-grid .wide{grid-column:span 2}.integration-choices{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;max-height:260px;overflow:auto;margin:12px 0}.integration-choices label,.integration-inline{display:flex!important;align-items:center;gap:7px!important;font-weight:400!important}.integration-center input[type=checkbox]{width:16px;height:16px;flex-shrink:0}.integration-center summary{font-weight:700;cursor:pointer;font-size:13px}.integration-alert{padding:13px 16px;border:1px solid #bfdbfe;border-radius:9px;background:#eff6ff;color:#1e40af;overflow-wrap:anywhere}.integration-alert.error{border-color:#fecaca;background:#fff1f2;color:#991b1b}.integration-secret{border-color:#f2ce77;background:#fffbeb}.integration-secret textarea{font-family:monospace}.integration-confirm{border-color:#f2ce77}.integration-table{overflow:auto;border:1px solid #dfe7f1;border-radius:12px;background:#fff}.integration-table table{margin:0;min-width:600px;width:100%;border-collapse:collapse}.integration-table td,.integration-table th{padding:13px;text-align:left;border-bottom:1px solid #edf2f7;font-size:12px;vertical-align:top}.integration-table th{background:#f8fafc;color:#65758d}.integration-table small,.integration-table code{display:block;max-width:410px;overflow-wrap:anywhere;white-space:normal;margin:4px 0}.integration-center code{font-family:ui-monospace,monospace;font-size:12px;overflow-wrap:anywhere}.integration-center pre{background:#eef3fa;border-radius:8px;padding:14px;overflow:auto;white-space:pre-wrap;font-size:12px}@media(max-width:700px){.integration-dialog{width:100%;max-width:100%;max-height:100dvh;height:100dvh;margin:0;border-radius:0}.integration-header,.integration-body{padding:16px}.integration-header h2{font-size:19px}.integration-tabs{padding:9px 12px}.integration-grid{grid-template-columns:1fr}.integration-grid .wide{grid-column:auto}.integration-choices{grid-template-columns:1fr}.integration-card{padding:16px}.integration-actions .integration-button{flex:1}.integration-toolbar .integration-button{flex:0}}
</style>
