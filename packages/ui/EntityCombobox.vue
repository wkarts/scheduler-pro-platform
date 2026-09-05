<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

export type EntityOption = { id: string; label: string; detail?: string; disabled?: boolean }
const props = withDefaults(defineProps<{
  modelValue: string
  text?: string
  options: EntityOption[]
  label: string
  placeholder?: string
  allowCustom?: boolean
  required?: boolean
  disabled?: boolean
  maxlength?: number
  search?: (query: string, signal: AbortSignal) => Promise<EntityOption[]>
}>(), { allowCustom: false, required: false, disabled: false, maxlength: 160, placeholder: 'Digite para buscar' })
const emit = defineEmits<{
  'update:modelValue': [value: string]
  'update:text': [value: string]
  select: [option: EntityOption]
  commit: [value: { id: string; text: string }]
}>()
const root = ref<HTMLElement | null>(null)
const input = ref<HTMLInputElement | null>(null)
const listId = `entity-${useId()}`
const query = ref(props.text || props.options.find(item => item.id === props.modelValue)?.label || '')
const opened = ref(false)
const cursor = ref(-1)
const loading = ref(false)
const failure = ref('')
const remote = ref<EntityOption[]>([])
let epoch = 0
let timer: ReturnType<typeof setTimeout> | undefined
let blurTimer: ReturnType<typeof setTimeout> | undefined
let controller: AbortController | undefined
let remembered: EntityOption | undefined
const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim()
const exactName = (value: string) => value.normalize('NFC').toLocaleLowerCase('pt-BR').trim().replace(/\s+/g, ' ')
const source = computed(() => props.search ? remote.value : props.options)
const matches = computed(() => {
  const terms = normalize(query.value).split(/\s+/).filter(Boolean)
  return source.value.filter(item => terms.every(term => normalize(`${item.label} ${item.detail || ''}`).includes(term))).slice(0, 6)
})
const exact = computed(() => [...source.value, ...props.options].find(item => !item.disabled && exactName(item.label) === exactName(query.value)))
const custom = computed(() => props.allowCustom && query.value.trim() && !props.modelValue && !exact.value)
watch(() => [props.modelValue, props.text, props.options] as const, () => {
  const option = props.options.find(item => item.id === props.modelValue) || (remembered?.id === props.modelValue ? remembered : undefined)
  if (props.modelValue && option) query.value = option.label
  else if (!props.modelValue && props.text !== undefined) query.value = props.text
  else if (!props.modelValue && !opened.value) query.value = ''
})
function searchSoon(): void {
  cursor.value = -1
  failure.value = ''
  if (!props.search) return
  clearTimeout(timer); controller?.abort()
  const request = ++epoch
  timer = setTimeout(async () => {
    controller = new AbortController(); loading.value = true
    try {
      const items = await props.search!(query.value.trim(), controller.signal)
      if (request === epoch) remote.value = items
    } catch (error) {
      if (request === epoch && !(error instanceof DOMException && error.name === 'AbortError')) failure.value = 'Busca indisponível. Tente novamente.'
    } finally { if (request === epoch) loading.value = false }
  }, 180)
}
function type(event: Event): void {
  query.value = (event.target as HTMLInputElement).value
  remembered = undefined
  emit('update:modelValue', '')
  emit('update:text', query.value)
  opened.value = true
  searchSoon()
}
function focus(): void { opened.value = true; searchSoon() }
function choose(item: EntityOption): void {
  if (item.disabled) return
  remembered = item; query.value = item.label
  emit('update:modelValue', item.id); emit('update:text', item.label); emit('select', item)
  emit('commit', { id: item.id, text: item.label })
  opened.value = false; cursor.value = -1
}
function finalize(): void {
  if (exact.value && query.value.trim() && !props.modelValue) { choose(exact.value); return }
  if (!props.modelValue) {
    const value = props.allowCustom ? query.value.trim().replace(/\s+/g, ' ') : ''
    query.value = value; emit('update:text', value); emit('commit', { id: '', text: value })
  }
  opened.value = false; cursor.value = -1
}
function blur(): void {
  clearTimeout(blurTimer)
  blurTimer = setTimeout(() => { if (!root.value?.contains(document.activeElement)) finalize() }, 120)
}
function clear(): void {
  remembered = undefined; query.value = ''; emit('update:modelValue', ''); emit('update:text', '')
  emit('commit', { id: '', text: '' }); input.value?.focus(); opened.value = false
}
function keyboard(event: KeyboardEvent): void {
  if (event.isComposing) return
  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); opened.value = false; cursor.value = -1; return }
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault(); opened.value = true
    const delta = event.key === 'ArrowDown' ? 1 : -1
    for (let step=0; step<matches.value.length; step++) { cursor.value=(cursor.value+delta+matches.value.length)%matches.value.length; if (!matches.value[cursor.value]?.disabled) break }
    void nextTick(() => document.getElementById(`${listId}-${cursor.value}`)?.scrollIntoView({ block: 'nearest' }))
  } else if (event.key === 'Enter' && opened.value) {
    event.preventDefault()
    const item = matches.value[cursor.value]
    if (item) choose(item); else finalize()
  } else if (event.key === 'Tab') finalize()
}
// No requests survive unmount; stale responses cannot select a different record.
onBeforeUnmount(() => { epoch++; controller?.abort(); clearTimeout(timer); clearTimeout(blurTimer) })
</script>

<template>
  <div ref="root" class="entity-combobox" @focusout="blur">
    <div class="entity-entry">
      <input ref="input" :value="query" type="text" role="combobox" aria-autocomplete="list" :aria-label="label"
        :aria-expanded="opened" :aria-controls="listId" :aria-activedescendant="opened && cursor >= 0 ? `${listId}-${cursor}` : undefined"
        :placeholder="placeholder" :maxlength="maxlength" :required="required" :disabled="disabled"
        autocomplete="off" @input="type" @focus="focus" @keydown="keyboard">
      <button v-if="query && !disabled" type="button" class="entity-clear" :aria-label="`Limpar ${label}`" @click="clear">×</button>
    </div>
    <div v-if="opened && !disabled" class="entity-suggestions">
      <div v-if="loading" role="status" class="entity-hint">Buscando…</div>
      <div v-if="failure" role="alert" class="entity-hint">{{ failure }}</div>
      <ul :id="listId" role="listbox" :aria-label="label">
        <li v-for="(item, index) in matches" :id="`${listId}-${index}`" :key="item.id" role="option"
          :aria-selected="modelValue === item.id" :aria-disabled="item.disabled || undefined"
          :class="{ highlighted: cursor === index, disabled: item.disabled }"
          @mousedown.prevent @click="choose(item)"><strong>{{ item.label }}</strong><small v-if="item.detail">{{ item.detail }}</small></li>
      </ul>
      <p v-if="!loading && !matches.length" class="entity-hint">{{ allowCustom ? 'Nenhum cadastro encontrado. O texto digitado será usado.' : 'Nenhum resultado. Digite outro termo.' }}</p>
      <p v-if="custom" class="entity-hint">Novo: <strong>{{ query }}</strong>. Continue para o próximo campo.</p>
    </div>
    <small v-if="custom && !opened" class="entity-new">Novo cadastro ao salvar: {{ query }}</small>
  </div>
</template>

<style scoped>
.entity-combobox{position:relative;min-width:0;width:100%;text-transform:none;letter-spacing:normal}.entity-entry{position:relative}.entity-entry input{width:100%;box-sizing:border-box;min-height:44px;padding:10px 40px 10px 12px;border:1px solid #cbd7e6;border-radius:11px;background:#fff;color:#142943;font:inherit;font-size:14px;outline:none}.entity-entry input:focus{outline:2px solid #93b9ff;outline-offset:1px}.entity-clear{position:absolute;right:3px;top:3px;width:36px;height:38px;border:0;background:transparent;color:#52657e;font-size:24px;cursor:pointer}.entity-suggestions{position:absolute;inset:auto 0;top:calc(100% + 3px);z-index:20;max-height:min(250px,35dvh);overflow:auto;overscroll-behavior:contain;border:1px solid #cbd7e6;border-radius:11px;background:white;box-shadow:0 9px 24px #10254822;font-weight:400}.entity-suggestions ul{list-style:none;padding:4px;margin:0}.entity-suggestions li{min-height:44px;box-sizing:border-box;padding:9px 10px;display:grid;gap:3px;border-radius:8px;cursor:pointer;color:#172b48}.entity-suggestions li strong{font-size:14px;font-weight:600;overflow-wrap:anywhere}.entity-suggestions li small{font-size:12px;color:#65758d}.entity-suggestions li:hover,.entity-suggestions li.highlighted{background:#eff6ff}.entity-suggestions li[aria-selected=true]{background:#e0edff}.entity-suggestions li.disabled{opacity:.5;cursor:not-allowed}.entity-hint{padding:9px 12px;margin:0;font-size:12px;color:#52657e}.entity-new{display:block;margin-top:6px;font-size:12px;color:#315ca4}@media(max-width:700px){.entity-entry input{font-size:16px}.entity-suggestions{max-height:30dvh}}
</style>
