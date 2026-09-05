<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

type Api = <T>(path: string, method?: string, payload?: unknown) => Promise<T>
type Receiver = { id: string; name: string; auth_mode: 'hmac' | 'bearer'; events: string[]; active: boolean; rate_limit: number; receive_path: string; revoked_at: string | null; last_received_at: string | null }
type Receipt = { id: string; receiver_id: string; receiver_name: string; external_id: string; event_type: string; state: string; received_at: string; payload_available: boolean }
const props = defineProps<{ api: Api; enabled: boolean }>()
const emit = defineEmits<{ secret: [title: string, value: string] }>()
const section = ref<'receivers' | 'inbox'>('receivers')
const receivers = ref<Receiver[]>([])
const receipts = ref<Receipt[]>([])
const detail = ref<Record<string, unknown> | null>(null)
const error = ref('')
const notice = ref('')
const busy = ref(false)
const offset = ref(0)
const editing = ref<string | null>(null)
const form = ref({ name: '', auth_mode: 'hmac' as 'hmac' | 'bearer', events: '*', active: true, rate_limit: 120 })
const confirmation = ref<{ message: string; run: () => Promise<void> } | null>(null)
let mounted = true
function url(item: Receiver): string { return window.location.origin + item.receive_path }
function date(value: string | null): string { return value ? new Date(value).toLocaleString('pt-BR') : '—' }
function state(value: string): string { return ({ received: 'Recebido', acknowledged: 'Conferido', ignored: 'Ignorado' } as Record<string, string>)[value] || value }
async function load(): Promise<void> {
  const target = section.value
  const result = await props.api<Receiver[] | Receipt[]>(target === 'receivers' ? '/receivers' : `/inbox?offset=${offset.value}`)
  if (!mounted || target !== section.value) return
  if (target === 'receivers') receivers.value = result as Receiver[]
  else receipts.value = result as Receipt[]
}
async function execute(action?: () => Promise<void>): Promise<void> {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { if (action) await action(); await load() }
  catch (failure) { if (mounted) error.value = failure instanceof Error ? failure.message : 'Falha na operação.' }
  finally { if (mounted) busy.value = false }
}
function reset(): void { editing.value = null; form.value = { name: '', auth_mode: 'hmac', events: '*', active: true, rate_limit: 120 } }
function edit(item: Receiver): void { editing.value = item.id; form.value = { name: item.name, auth_mode: item.auth_mode, events: item.events.join(', '), active: item.active, rate_limit: item.rate_limit } }
function switchSection(next: 'receivers' | 'inbox'): void { if (busy.value) return; section.value = next; offset.value = 0; detail.value = null; void execute() }
async function save(): Promise<void> {
  await execute(async () => {
    const payload = { name: form.value.name, events: form.value.events.split(',').map(e => e.trim()).filter(Boolean), active: form.value.active, rate_limit: form.value.rate_limit }
    const result = await props.api<{ secret?: string }>(editing.value ? `/receivers/${editing.value}` : '/receivers', editing.value ? 'PUT' : 'POST', editing.value ? payload : { ...payload, auth_mode: form.value.auth_mode })
    if (mounted && result.secret) emit('secret', 'Credencial do webhook de entrada — guarde agora', result.secret)
    reset(); notice.value = 'Receptor salvo. Utilize a URL e a credencial no sistema remetente.'
  })
}
function ask(message: string, run: () => Promise<void>): void { confirmation.value = { message, run } }
async function confirm(): Promise<void> { const run = confirmation.value?.run; confirmation.value = null; await execute(run) }
function rotate(item: Receiver): void {
  ask(`Rotacionar a credencial de ${item.name}? A anterior deixará de funcionar.`, async () => {
    const result = await props.api<{ secret: string }>(`/receivers/${item.id}/rotate-secret`, 'POST', {})
    if (mounted) emit('secret', 'Nova credencial de entrada — atualize o remetente', result.secret)
  })
}
function revoke(item: Receiver): void { ask(`Revogar ${item.name}? Esta URL deixará de aceitar eventos. O histórico será preservado.`, async () => { await props.api(`/receivers/${item.id}`, 'DELETE') }) }
async function copyUrl(item: Receiver): Promise<void> { try { await navigator.clipboard.writeText(url(item)); notice.value = 'URL copiada.' } catch { error.value = 'Selecione e copie a URL do receptor.' } }
async function inspect(item: Receipt): Promise<void> { await execute(async () => { const result = await props.api<Record<string, unknown>>(`/inbox/${item.id}`); if (mounted) detail.value = result }) }
async function review(item: Receipt, next: 'acknowledged' | 'ignored'): Promise<void> { await execute(async () => { await props.api(`/inbox/${item.id}/status`, 'PATCH', { state: next }); detail.value = null }) }
function discard(item: Receipt): void { ask('Descartar o conteúdo deste evento? A marca de duplicidade será preservada, mas o conteúdo não poderá ser recuperado aqui.', async () => { await props.api(`/inbox/${item.id}/payload`, 'DELETE'); detail.value = null }) }
onMounted(() => { void execute() })
onUnmounted(() => { mounted = false; detail.value = null; confirmation.value = null })
</script>

<template>
  <section class="incoming-panel" aria-label="Webhooks de entrada">
    <p class="explanation">Receba eventos externos em uma URL da plataforma. Cada receptor tem credencial independente e sem expiração obrigatória. Pausa, revogação e rotação permanecem disponíveis.</p>
    <p class="explanation"><strong>Receber não significa executar:</strong> o evento fica registrado para consulta ou consumo autenticado pela API. Não cria ou altera agendamentos automaticamente.</p>
    <div v-if="!enabled" role="status" class="message">Recebimento desativado na configuração do serviço.</div>
    <div v-if="error" role="alert" class="message error">{{ error }}</div>
    <div v-if="notice" role="status" class="message">{{ notice }}</div>
    <nav class="actions" aria-label="Gestão de entrada"><button :class="{ primary: section === 'receivers' }" :disabled="busy" @click="switchSection('receivers')">Receptores</button><button :class="{ primary: section === 'inbox' }" :disabled="busy" @click="switchSection('inbox')">Recebidos</button><button :disabled="busy" @click="execute()">{{ busy ? 'Atualizando…' : 'Atualizar' }}</button></nav>
    <section v-if="confirmation" role="alertdialog" aria-label="Confirmar operação de entrada" class="card"><p>{{ confirmation.message }}</p><div class="actions"><button class="primary" :disabled="busy" @click="confirm">Confirmar</button><button @click="confirmation = null">Cancelar</button></div></section>
    <template v-if="section === 'receivers'">
      <form class="card" @submit.prevent="save">
        <h3>{{ editing ? 'Editar receptor' : 'Novo receptor de eventos' }}</h3>
        <div class="fields"><label>Nome da integração<input v-model="form.name" minlength="2" maxlength="100" required placeholder="ERP / financeiro / automação"></label><label>Requisições por minuto<input v-model.number="form.rate_limit" type="number" min="1" max="1000" required></label></div>
        <fieldset :disabled="Boolean(editing) || busy"><legend>Autenticação do remetente</legend><label class="inline"><input v-model="form.auth_mode" type="radio" value="hmac">Assinatura HMAC-SHA256 (recomendada)</label><label class="inline"><input v-model="form.auth_mode" type="radio" value="bearer">Token Bearer exclusivo deste receptor</label></fieldset>
        <label>Tipos de evento permitidos<input v-model="form.events" required maxlength="10000" placeholder="pedido.atualizado, pagamento.confirmado"><small>Separe por vírgula. Use * para aceitar qualquer tipo do contrato JSON.</small></label>
        <p class="explanation">Validade: <strong>sem expiração</strong>. O segredo é exibido somente na criação ou rotação. Não é o token de acesso da API.</p>
        <label class="inline"><input v-model="form.active" type="checkbox">Receptor ativo</label>
        <div class="actions"><button class="primary" :disabled="busy" type="submit">{{ editing ? 'Salvar receptor' : 'Criar receptor' }}</button><button v-if="editing" type="button" @click="reset">Cancelar edição</button></div>
      </form>
      <article v-for="item in receivers" :key="item.id" class="card">
        <h3>{{ item.name }} <small>{{ item.revoked_at ? 'Revogado' : item.active ? 'Ativo' : 'Pausado' }}</small></h3>
        <code>{{ url(item) }}</code>
        <p>{{ item.auth_mode === 'hmac' ? 'HMAC-SHA256' : 'Bearer' }} · Sem expiração · Último recebimento: {{ date(item.last_received_at) }}</p><small>Eventos: {{ item.events.join(', ') }}</small>
        <div class="actions"><button @click="copyUrl(item)">Copiar URL</button><button :disabled="busy || Boolean(item.revoked_at)" @click="edit(item)">Editar</button><button :disabled="busy || Boolean(item.revoked_at)" @click="execute(async () => { await props.api(`/receivers/${item.id}/status`, 'PATCH', { active: !item.active }) })">{{ item.active ? 'Pausar' : 'Ativar' }}</button><button :disabled="busy || Boolean(item.revoked_at)" @click="rotate(item)">Rotacionar credencial</button><button :disabled="busy || Boolean(item.revoked_at)" @click="revoke(item)">Revogar</button></div>
      </article>
      <p v-if="!receivers.length && !busy">Nenhum receptor cadastrado.</p>
      <details class="card"><summary>Contrato de recebimento</summary><p>Envie <code>POST</code> para a URL do receptor, com <code>Content-Type: application/json</code> e um objeto com <code>id</code>, <code>type</code> e <code>data</code>. Reenvios devem preservar id e conteúdo.</p><pre>{ "id": "evento-001", "type": "pedido.atualizado", "data": { "referencia": "123" } }</pre><p>Bearer: <code>Authorization: Bearer CREDENCIAL_DO_RECEPTOR</code>.</p><p>HMAC: envie <code>X-Scheduler-Timestamp</code>, <code>X-Scheduler-Delivery-Id</code> e <code>X-Scheduler-Signature: v1=HEX</code>. Assine timestamp + ponto + delivery-id + ponto + os bytes exatos do JSON. Tolerância do relógio: cinco minutos.</p><p>Resposta 202: evento armazenado. Resposta 200 com duplicate=true: já recebido. 409: mesmo id com conteúdo diferente. Outros fornecedores podem exigir adaptação do formato ou da assinatura.</p></details>
    </template>
    <template v-else>
      <article v-for="item in receipts" :key="item.id" class="card"><h3>{{ item.event_type }} <small>{{ state(item.state) }}</small></h3><p>{{ item.receiver_name }} · {{ date(item.received_at) }}</p><code>Evento: {{ item.external_id }}</code><code>Recebimento: {{ item.id }}</code><div class="actions"><button :disabled="busy" @click="inspect(item)">Consultar</button><button :disabled="busy || item.state === 'acknowledged'" @click="review(item, 'acknowledged')">Marcar conferido</button><button :disabled="busy || item.state === 'ignored'" @click="review(item, 'ignored')">Ignorar</button><button :disabled="busy || !item.payload_available || item.state === 'received'" @click="discard(item)">Descartar conteúdo</button></div><small v-if="!item.payload_available">Conteúdo expirado ou descartado; deduplicação preservada.</small></article>
      <p v-if="!receipts.length && !busy">Nenhum evento recebido nesta página.</p>
      <div class="actions"><button :disabled="busy || offset === 0" @click="offset = Math.max(0, offset - 50); execute()">Anterior</button><span>Página {{ offset / 50 + 1 }}</span><button :disabled="busy || receipts.length < 50" @click="offset += 50; execute()">Próxima</button></div>
      <section v-if="detail" class="card"><h3>Detalhes do recebimento</h3><pre>{{ JSON.stringify(detail, null, 2) }}</pre><button @click="detail = null">Ocultar conteúdo</button></section>
    </template>
  </section>
</template>

<style scoped>
.incoming-panel{display:grid;gap:16px;min-width:0;color:#172b48}.card{padding:22px;border:1px solid #dfe7f1;border-radius:12px;background:#fff;display:grid;gap:14px;min-width:0}.card h3{margin:0;font-size:17px}.card p,.explanation{margin:0;color:#65758d;font-size:13px;line-height:1.6}.actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.fields{display:grid;grid-template-columns:2fr 1fr;gap:16px}label{display:grid;gap:7px;font-size:12px;font-weight:700;color:#415773}.inline{display:flex;align-items:center;gap:8px;font-weight:400}input:not([type=checkbox]):not([type=radio]){width:100%;border:1px solid #cfdbea;border-radius:8px;padding:11px;background:#fff;color:#172b48;font:inherit}input[type=radio],input[type=checkbox]{width:17px;height:17px;flex-shrink:0}button{border:1px solid #cfdbea;background:#fff;color:#233b5c;padding:9px 13px;border-radius:9px;font-size:12px;font-weight:700;min-height:40px;cursor:pointer}button.primary{background:var(--blue,#2563eb);color:#fff;border-color:var(--blue,#2563eb)}button:disabled{opacity:.45;cursor:not-allowed}button:focus-visible,input:focus-visible{outline:2px solid #93b9ff;outline-offset:2px}fieldset{display:grid;gap:10px;border:1px solid #dfe7f1;border-radius:8px;padding:14px}legend{font-size:12px;font-weight:700}code{font:12px ui-monospace,monospace;overflow-wrap:anywhere}pre{padding:14px;white-space:pre-wrap;overflow-wrap:anywhere;overflow:auto;max-height:55vh;background:#eef3fa;border-radius:8px;font-size:12px;margin:0}small{font-size:12px;font-weight:400;color:#65758d}.message{padding:13px 16px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:9px;color:#1e40af;overflow-wrap:anywhere}.message.error{color:#991b1b;background:#fff1f2;border-color:#fecaca}summary{cursor:pointer;font-weight:700}@media(max-width:700px){.fields{grid-template-columns:1fr}.card{padding:16px}.actions button{flex:1}}
</style>
