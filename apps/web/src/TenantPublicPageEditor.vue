<script setup lang="ts">
import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  watch,
  type CSSProperties,
} from 'vue'
import {
  ArrowDown,
  ArrowUp,
  Clipboard,
  Copy,
  Eye,
  GripVertical,
  History,
  LayoutTemplate,
  Menu,
  Monitor,
  Palette,
  Plus,
  RotateCcw,
  Save,
  Settings2,
  Smartphone,
  Tablet,
  Trash2,
  Upload,
  X,
} from 'lucide-vue-next'

type Device = 'desktop' | 'tablet' | 'mobile'
type SideTab = 'elements' | 'structure' | 'templates'
type InspectorTab = 'content' | 'style' | 'responsive' | 'global' | 'history'
type Envelope<T> = { data?: T; error?: { message?: string } }
type Template = { key: string; name: string; description: string; segment: string }
type Version = {
  id: string
  version_number: number
  label?: string | null
  created_at?: string
  published: boolean
  draft: boolean
}
type ResponsiveStyles = {
  desktop: CSSProperties
  tablet: CSSProperties
  mobile: CSSProperties
  hidden: Record<Device, boolean>
}
type Block = {
  id: string
  type: string
  props: Record<string, unknown>
  style: CSSProperties
  responsive: ResponsiveStyles
}
type PageContent = {
  version: number
  title?: string
  global_styles: Record<string, unknown>
  seo: Record<string, unknown>
  blocks: Block[]
}
type EditorState = {
  id?: string
  slug: string
  status: string
  template_key?: string | null
  current_version_id?: string | null
  draft_version_id?: string | null
  version_number?: number | null
  content: PageContent
  published_content?: PageContent | null
  versions: Version[]
}

const ELEMENTS = [
  ['section', 'Seção'], ['container', 'Container'], ['columns', 'Colunas'], ['grid', 'Grid'],
  ['hero', 'Hero'], ['title', 'Título'], ['subtitle', 'Subtítulo'], ['text', 'Texto'], ['logo', 'Logo'],
  ['image', 'Imagem'], ['gallery', 'Galeria'], ['video', 'Vídeo seguro'], ['button', 'Botão'],
  ['whatsapp_button', 'Botão WhatsApp'], ['social', 'Redes sociais'], ['divider', 'Divisor'], ['spacer', 'Espaço'],
  ['card', 'Card'], ['services', 'Serviços'], ['professionals', 'Profissionais'], ['booking', 'Calendário / Agenda'],
  ['form', 'Formulário'], ['business_hours', 'Horário de funcionamento'], ['address', 'Endereço'], ['map', 'Mapa'],
  ['contact', 'Contato'], ['faq', 'FAQ'], ['testimonials', 'Depoimentos'], ['cta', 'CTA'], ['notices', 'Avisos'],
  ['policies', 'Políticas'], ['footer', 'Rodapé'],
] as const

const pageSlug = 'home'
const portalReady = ref(false)
const active = ref(false)
const loading = ref(false)
const saving = ref(false)
const publishing = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const templates = ref<Template[]>([])
const state = ref<EditorState | null>(null)
const content = ref<PageContent>({ version: 2, global_styles: {}, seo: {}, blocks: [] })
const selectedId = ref('')
const device = ref<Device>('desktop')
const sideTab = ref<SideTab>('elements')
const inspectorTab = ref<InspectorTab>('content')
const leftOpen = ref(true)
const rightOpen = ref(true)
const draggingId = ref('')
const clipboard = ref<Block | null>(null)
const dirty = ref(false)
let autosaveTimer: number | undefined
let editGeneration = 0
let saveGeneration = 0

const selectedBlock = computed(() => content.value.blocks.find(item => item.id === selectedId.value) || null)
const canvasWidth = computed(() => device.value === 'mobile' ? '390px' : device.value === 'tablet' ? '820px' : '1180px')
const globalStyles = computed(() => content.value.global_styles || {})

function uid(type: string): string {
  return `${type}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}
function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}
function emptyResponsive(): ResponsiveStyles {
  return {
    desktop: {}, tablet: {}, mobile: {},
    hidden: { desktop: false, tablet: false, mobile: false },
  }
}
function defaultBlock(type: string): Block {
  const defaults: Record<string, Record<string, unknown>> = {
    section: { title: 'Nova seção' },
    container: { title: 'Container' },
    columns: { columns: 2 },
    grid: { columns: 3 },
    hero: { eyebrow: 'Seu estabelecimento', title: 'Agende seu horário', text: 'Apresente aqui sua proposta de valor.', cta: 'Agendar agora', image: '' },
    title: { text: 'Novo título' },
    subtitle: { text: 'Novo subtítulo' },
    text: { text: 'Escreva seu conteúdo aqui.' },
    logo: { image: '', alt: 'Logomarca' },
    image: { image: '', alt: 'Imagem' },
    gallery: { title: 'Galeria', layout: 'grid', images: [] },
    video: { title: 'Vídeo', url: '' },
    button: { label: 'Saiba mais', url: '#' },
    whatsapp_button: { label: 'Falar pelo WhatsApp', phone: '' },
    social: { title: 'Redes sociais', instagram: '', facebook: '', tiktok: '' },
    divider: {}, spacer: { height: 32 },
    card: { title: 'Card', text: 'Conteúdo do card' },
    services: { title: 'Serviços', subtitle: 'Conheça as opções', show_prices: true },
    professionals: { title: 'Profissionais', layout: 'cards' },
    booking: { title: 'Agende seu horário', subtitle: 'Escolha a melhor data e horário.' },
    form: { title: 'Formulário' },
    business_hours: { title: 'Horário de funcionamento' },
    address: { title: 'Onde estamos', address: '', show_map: true },
    map: { title: 'Localização', address: '' },
    contact: { title: 'Contato', phone: '', email: '' },
    faq: { title: 'Perguntas frequentes', items: [] },
    testimonials: { title: 'Depoimentos', items: [] },
    cta: { title: 'Pronto para agendar?', text: 'Escolha um horário disponível.', button: 'Agendar' },
    notices: { title: 'Avisos', text: '' },
    policies: { title: 'Políticas', text: '' },
    footer: { text: 'Obrigado pela visita.' },
  }
  return {
    id: uid(type), type,
    props: clone(defaults[type] || { title: 'Novo bloco' }),
    style: {}, responsive: emptyResponsive(),
  }
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    cache: 'no-store',
    headers: {
      accept: 'application/json',
      ...(init.body ? { 'content-type': 'application/json' } : {}),
      ...(init.headers || {}),
    },
  })
  const body = await response.json().catch(() => ({})) as Envelope<T>
  if (!response.ok) throw new Error(body.error?.message || `Falha HTTP ${response.status}`)
  return body.data as T
}
function toast(message: string): void {
  successMessage.value = message
  window.setTimeout(() => { if (successMessage.value === message) successMessage.value = '' }, 3500)
}
function fail(error: unknown, fallback: string): void {
  errorMessage.value = error instanceof Error ? error.message : fallback
}
function normalizeContent(value: PageContent | undefined | null): PageContent {
  const candidate = clone(value || ({ version: 2, global_styles: {}, seo: {}, blocks: [] } as PageContent))
  candidate.version = Number(candidate.version || 2)
  candidate.global_styles = candidate.global_styles || {}
  candidate.seo = candidate.seo || {}
  candidate.blocks = Array.isArray(candidate.blocks) ? candidate.blocks : []
  candidate.blocks = candidate.blocks.map(item => ({
    ...item,
    id: item.id || uid(item.type || 'block'),
    type: item.type || 'text',
    props: item.props || {},
    style: (item.style || {}) as CSSProperties,
    responsive: {
      desktop: { ...(item.responsive?.desktop || {}) },
      tablet: { ...(item.responsive?.tablet || {}) },
      mobile: { ...(item.responsive?.mobile || {}) },
      hidden: {
        ...emptyResponsive().hidden,
        ...(item.responsive?.hidden || {}),
      },
    },
  }))
  return candidate
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const [available, current] = await Promise.all([
      api<Template[]>('/landing-pages/templates'),
      api<EditorState>(`/landing-pages/${pageSlug}`),
    ])
    templates.value = available
    state.value = current
    content.value = normalizeContent(current.content)
    selectedId.value = content.value.blocks[0]?.id || ''
    dirty.value = false
  } catch (error) {
    fail(error, 'Não foi possível abrir o editor.')
  } finally {
    loading.value = false
  }
}
async function open(): Promise<void> { active.value = true; await load() }
function close(): void {
  if (dirty.value) void saveNow('Autosave ao fechar')
  active.value = false
}
function markDirty(): void {
  dirty.value = true
  editGeneration += 1
  if (autosaveTimer !== undefined) window.clearTimeout(autosaveTimer)
  autosaveTimer = window.setTimeout(() => void autosave(), 900)
}
function selectBlock(block: Block): void {
  selectedId.value = block.id
  if (window.innerWidth < 760) rightOpen.value = true
}
function addBlock(type: string, index?: number): void {
  const block = defaultBlock(type)
  const at = index === undefined ? content.value.blocks.length : index
  content.value.blocks.splice(at, 0, block)
  selectedId.value = block.id
  markDirty()
}
function removeBlock(block: Block): void {
  const index = content.value.blocks.findIndex(item => item.id === block.id)
  if (index < 0) return
  content.value.blocks.splice(index, 1)
  selectedId.value = content.value.blocks[Math.min(index, content.value.blocks.length - 1)]?.id || ''
  markDirty()
}
function duplicateBlock(block: Block): void {
  const index = content.value.blocks.findIndex(item => item.id === block.id)
  const copy = clone(block)
  copy.id = uid(block.type)
  content.value.blocks.splice(index + 1, 0, copy)
  selectedId.value = copy.id
  markDirty()
}
function copyBlock(block: Block): void { clipboard.value = clone(block); toast('Bloco copiado.') }
function pasteBlock(): void {
  if (!clipboard.value) return
  const copy = clone(clipboard.value)
  copy.id = uid(copy.type)
  const current = content.value.blocks.findIndex(item => item.id === selectedId.value)
  content.value.blocks.splice(current < 0 ? content.value.blocks.length : current + 1, 0, copy)
  selectedId.value = copy.id
  markDirty()
}
function moveBlock(block: Block, delta: number): void {
  const index = content.value.blocks.findIndex(item => item.id === block.id)
  const target = index + delta
  if (index < 0 || target < 0 || target >= content.value.blocks.length) return
  const [item] = content.value.blocks.splice(index, 1)
  if (!item) return
  content.value.blocks.splice(target, 0, item)
  markDirty()
}
function dragStart(block: Block, event: DragEvent): void {
  draggingId.value = block.id
  event.dataTransfer?.setData('text/plain', block.id)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}
function dropOn(target: Block, event: DragEvent): void {
  event.preventDefault()
  const sourceId = event.dataTransfer?.getData('text/plain') || draggingId.value
  if (!sourceId || sourceId === target.id) return
  const from = content.value.blocks.findIndex(item => item.id === sourceId)
  const to = content.value.blocks.findIndex(item => item.id === target.id)
  if (from < 0 || to < 0) return
  const [item] = content.value.blocks.splice(from, 1)
  if (!item) return
  content.value.blocks.splice(to, 0, item)
  draggingId.value = ''
  markDirty()
}
function updateProp(key: string, value: unknown): void {
  if (!selectedBlock.value) return
  selectedBlock.value.props[key] = value
  markDirty()
}
function updateStyle(key: string, value: string | number): void {
  if (!selectedBlock.value) return
  Object.assign(selectedBlock.value.style, { [key]: value })
  markDirty()
}
function updateResponsive(key: string, value: string | number): void {
  if (!selectedBlock.value) return
  Object.assign(selectedBlock.value.responsive[device.value], { [key]: value })
  markDirty()
}
function toggleHidden(target: Device): void {
  if (!selectedBlock.value) return
  selectedBlock.value.responsive.hidden[target] = !selectedBlock.value.responsive.hidden[target]
  markDirty()
}
function updateGlobal(key: string, value: unknown): void { content.value.global_styles[key] = value; markDirty() }
function updateSeo(key: string, value: unknown): void { content.value.seo[key] = value; markDirty() }
function previewStyle(block: Block): CSSProperties {
  return { ...block.style, ...block.responsive[device.value] }
}

async function persistDraft(path: 'draft' | 'autosave', label?: string): Promise<void> {
  const generation = editGeneration
  const requestGeneration = ++saveGeneration
  saving.value = true
  try {
    const result = await api<{ version_id: string; version_number: number }>(
      `/landing-pages/${pageSlug}/${path}`,
      { method: 'POST', body: JSON.stringify(content.value) },
    )
    if (requestGeneration === saveGeneration && generation === editGeneration) {
      dirty.value = false
      if (state.value) {
        state.value.draft_version_id = result.version_id
        state.value.version_number = result.version_number
      }
      if (label) toast(label)
    }
  } catch (error) {
    if (requestGeneration === saveGeneration) fail(error, path === 'autosave' ? 'Autosave falhou; suas alterações continuam nesta tela.' : 'Não foi possível salvar o rascunho.')
  } finally {
    if (requestGeneration === saveGeneration) saving.value = false
  }
}
async function saveNow(label = 'Rascunho salvo.'): Promise<void> { await persistDraft('draft', label) }
async function autosave(): Promise<void> {
  if (!dirty.value || saving.value || publishing.value) return
  await persistDraft('autosave')
}
async function publish(): Promise<void> {
  publishing.value = true
  errorMessage.value = ''
  try {
    if (dirty.value) await saveNow('Alterações salvas.')
    await api(`/landing-pages/${pageSlug}/publish`, {
      method: 'POST',
      body: JSON.stringify({ version_id: state.value?.draft_version_id || null }),
    })
    state.value = await api<EditorState>(`/landing-pages/${pageSlug}`)
    content.value = normalizeContent(state.value.content)
    toast('Nova versão publicada.')
  } catch (error) {
    fail(error, 'Não foi possível publicar.')
  } finally {
    publishing.value = false
  }
}
async function applyTemplate(template: Template): Promise<void> {
  if (!window.confirm(`Criar um novo rascunho usando o modelo “${template.name}”? A versão publicada não será alterada.`)) return
  loading.value = true
  try {
    await api(`/landing-pages/${pageSlug}/templates/${template.key}`, { method: 'POST', body: '{}' })
    await load()
    sideTab.value = 'structure'
    toast(`Modelo ${template.name} aplicado ao rascunho.`)
  } catch (error) {
    fail(error, 'Não foi possível aplicar o modelo.')
  } finally {
    loading.value = false
  }
}
async function restoreVersion(version: Version): Promise<void> {
  if (!window.confirm(`Restaurar a versão ${version.version_number} como um novo rascunho?`)) return
  loading.value = true
  try {
    await api(`/landing-pages/${pageSlug}/versions/${version.id}/restore`, { method: 'POST', body: '{}' })
    await load()
    toast(`Versão ${version.version_number} restaurada em novo rascunho.`)
  } catch (error) {
    fail(error, 'Não foi possível restaurar a versão.')
  } finally {
    loading.value = false
  }
}
async function refreshHistory(): Promise<void> {
  if (state.value) state.value.versions = await api<Version[]>(`/landing-pages/${pageSlug}/versions`)
}

function cardTitle(block: Block): string {
  return String(block.props.title || block.props.text || block.props.label || block.type)
}
function displayType(type: string): string {
  return ELEMENTS.find(item => item[0] === type)?.[1] || type
}
function beforeUnload(event: BeforeUnloadEvent): void {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

watch(inspectorTab, value => { if (value === 'history') void refreshHistory() })
watch(active, value => document.body.classList.toggle('sp-public-editor-open', value))
onMounted(async () => {
  await nextTick()
  window.requestAnimationFrame(() => {
    portalReady.value = Boolean(
      document.querySelector('.tenant-console .nav-list') &&
      document.querySelector('.tenant-console .main-content'),
    )
  })
  window.addEventListener('beforeunload', beforeUnload)
})
onUnmounted(() => {
  document.body.classList.remove('sp-public-editor-open')
  window.removeEventListener('beforeunload', beforeUnload)
  if (autosaveTimer !== undefined) window.clearTimeout(autosaveTimer)
})
</script>

<template>
  <Teleport v-if="portalReady" to=".tenant-console .nav-list">
    <button class="nav-item sp-page-editor-nav" @click="open"><LayoutTemplate :size="19"/><span>Página Pública</span></button>
  </Teleport>

  <Teleport v-if="portalReady && active" to="body">
    <section class="page-editor" role="dialog" aria-modal="true" aria-label="Editor visual da página pública">
      <header class="editor-topbar">
        <div class="editor-brand"><LayoutTemplate :size="20"/><div><strong>Página Pública</strong><small>{{ dirty ? 'Alterações pendentes' : saving ? 'Salvando…' : 'Rascunho sincronizado' }}</small></div></div>
        <div class="device-switcher">
          <button :class="{active:device==='desktop'}" title="Desktop" @click="device='desktop'"><Monitor :size="18"/></button>
          <button :class="{active:device==='tablet'}" title="Tablet" @click="device='tablet'"><Tablet :size="18"/></button>
          <button :class="{active:device==='mobile'}" title="Mobile" @click="device='mobile'"><Smartphone :size="18"/></button>
        </div>
        <div class="top-actions">
          <button class="soft mobile-panel" @click="leftOpen=!leftOpen"><Menu :size="17"/> Elementos</button>
          <button class="soft" :disabled="saving" @click="saveNow()"><Save :size="17"/> Salvar</button>
          <button class="soft" title="Alternar preview" @click="device=device==='desktop'?'mobile':'desktop'"><Eye :size="17"/><span class="desktop-label">Preview</span></button>
          <button class="publish" :disabled="publishing||saving" @click="publish"><Upload :size="17"/>{{ publishing?'Publicando…':'Publicar' }}</button>
          <button class="icon" aria-label="Fechar" @click="close"><X :size="19"/></button>
        </div>
      </header>

      <p v-if="errorMessage" class="editor-alert error">{{ errorMessage }}</p>
      <p v-if="successMessage" class="editor-alert success">{{ successMessage }}</p>

      <div class="editor-body">
        <aside class="editor-left" :class="{open:leftOpen}">
          <div class="side-tabs">
            <button :class="{active:sideTab==='elements'}" @click="sideTab='elements'"><Plus :size="16"/> Elementos</button>
            <button :class="{active:sideTab==='structure'}" @click="sideTab='structure'"><GripVertical :size="16"/> Estrutura</button>
            <button :class="{active:sideTab==='templates'}" @click="sideTab='templates'"><LayoutTemplate :size="16"/> Modelos</button>
          </div>

          <div v-if="sideTab==='elements'" class="element-list">
            <button v-for="item in ELEMENTS" :key="item[0]" @click="addBlock(item[0])"><Plus :size="15"/><span>{{ item[1] }}</span></button>
          </div>
          <div v-else-if="sideTab==='structure'" class="structure-list">
            <div
              v-for="(block,index) in content.blocks"
              :key="block.id"
              class="structure-item"
              :class="{selected:selectedId===block.id}"
              draggable="true"
              @dragstart="dragStart(block,$event)"
              @dragover.prevent
              @drop="dropOn(block,$event)"
              @click="selectBlock(block)"
            >
              <GripVertical :size="15"/>
              <div><strong>{{ displayType(block.type) }}</strong><small>{{ cardTitle(block) }}</small></div>
              <div class="mini-actions">
                <button :disabled="index===0" title="Subir" @click.stop="moveBlock(block,-1)"><ArrowUp :size="13"/></button>
                <button :disabled="index===content.blocks.length-1" title="Descer" @click.stop="moveBlock(block,1)"><ArrowDown :size="13"/></button>
              </div>
            </div>
            <div v-if="!content.blocks.length" class="empty-side">Adicione elementos ou escolha um modelo.</div>
          </div>
          <div v-else class="template-list">
            <button v-for="template in templates" :key="template.key" @click="applyTemplate(template)">
              <strong>{{ template.name }}</strong><span>{{ template.description }}</span><small>{{ template.segment }}</small>
            </button>
          </div>
        </aside>

        <main class="editor-stage" @click="leftOpen=false;rightOpen=false">
          <div v-if="loading" class="editor-loading">Carregando editor…</div>
          <div v-else class="canvas-frame" :style="{width:canvasWidth}">
            <div
              class="canvas-page"
              :style="{
                '--preview-primary':String(globalStyles.primary||'#3151cf'),
                '--preview-bg':String(globalStyles.background||'#ffffff'),
                '--preview-text':String(globalStyles.text||'#1d273a'),
              }"
              @click.stop
            >
              <div v-if="!content.blocks.length" class="canvas-empty">
                <LayoutTemplate :size="46"/><strong>Comece com um modelo profissional</strong>
                <span>Ou adicione elementos pela lateral.</span>
                <button @click="sideTab='templates';leftOpen=true">Escolher modelo</button>
              </div>
              <article
                v-for="block in content.blocks"
                v-show="!block.responsive.hidden[device]"
                :key="block.id"
                class="canvas-block"
                :class="[block.type,{selected:selectedId===block.id}]"
                :style="previewStyle(block)"
                draggable="true"
                @dragstart="dragStart(block,$event)"
                @dragover.prevent
                @drop="dropOn(block,$event)"
                @click.stop="selectBlock(block)"
              >
                <div v-if="selectedId===block.id" class="block-toolbar">
                  <span>{{ displayType(block.type) }}</span>
                  <button title="Copiar" @click.stop="copyBlock(block)"><Copy :size="13"/></button>
                  <button title="Duplicar" @click.stop="duplicateBlock(block)"><Clipboard :size="13"/></button>
                  <button title="Excluir" @click.stop="removeBlock(block)"><Trash2 :size="13"/></button>
                </div>
                <template v-if="block.type==='hero'"><small>{{ block.props.eyebrow }}</small><h1>{{ block.props.title }}</h1><p>{{ block.props.text }}</p><button>{{ block.props.cta }}</button></template>
                <template v-else-if="['title','subtitle','text'].includes(block.type)"><h2 v-if="block.type==='title'">{{ block.props.text }}</h2><h3 v-else-if="block.type==='subtitle'">{{ block.props.text }}</h3><p v-else>{{ block.props.text }}</p></template>
                <template v-else-if="block.type==='image'||block.type==='logo'"><div class="image-placeholder">{{ block.props.image?'Imagem configurada':'Adicionar imagem' }}</div></template>
                <template v-else-if="block.type==='gallery'"><h2>{{ block.props.title }}</h2><div class="fake-grid"><i v-for="n in 6" :key="n"></i></div></template>
                <template v-else-if="block.type==='services'"><h2>{{ block.props.title }}</h2><p>{{ block.props.subtitle }}</p><div class="fake-cards"><i v-for="n in 3" :key="n">Serviço {{ n }}</i></div></template>
                <template v-else-if="block.type==='professionals'"><h2>{{ block.props.title }}</h2><div class="fake-cards"><i v-for="n in 3" :key="n">Profissional {{ n }}</i></div></template>
                <template v-else-if="block.type==='booking'||block.type==='form'"><h2>{{ block.props.title }}</h2><p>{{ block.props.subtitle }}</p><div class="booking-preview"><span>Data</span><span>Horário</span><button>Agendar</button></div></template>
                <template v-else-if="block.type==='button'||block.type==='whatsapp_button'"><button>{{ block.props.label }}</button></template>
                <template v-else-if="block.type==='spacer'"><div :style="{height:`${Number(block.props.height||32)}px`}"></div></template>
                <template v-else-if="block.type==='divider'"><hr/></template>
                <template v-else><h2>{{ block.props.title||displayType(block.type) }}</h2><p v-if="block.props.text">{{ block.props.text }}</p><span class="block-hint">{{ displayType(block.type) }}</span></template>
              </article>
            </div>
          </div>
        </main>

        <aside class="editor-right" :class="{open:rightOpen}">
          <div class="inspector-tabs">
            <button :class="{active:inspectorTab==='content'}" @click="inspectorTab='content'">Conteúdo</button>
            <button :class="{active:inspectorTab==='style'}" @click="inspectorTab='style'">Estilo</button>
            <button :class="{active:inspectorTab==='responsive'}" @click="inspectorTab='responsive'">Responsivo</button>
            <button :class="{active:inspectorTab==='global'}" @click="inspectorTab='global'">Global</button>
            <button :class="{active:inspectorTab==='history'}" @click="inspectorTab='history'">Histórico</button>
          </div>
          <div class="inspector-scroll">
            <template v-if="inspectorTab==='history'">
              <div class="inspector-title"><History :size="18"/><div><strong>Histórico de versões</strong><small>Restaurar cria novo rascunho</small></div></div>
              <div class="history-list">
                <button v-for="version in state?.versions||[]" :key="version.id" @click="restoreVersion(version)">
                  <div><strong>Versão {{ version.version_number }}</strong><span>{{ version.label||'Rascunho' }}</span><small>{{ version.created_at?new Date(version.created_at).toLocaleString('pt-BR'):'' }}</small></div>
                  <em v-if="version.published">Publicada</em><em v-else-if="version.draft">Rascunho atual</em><RotateCcw v-else :size="15"/>
                </button>
              </div>
            </template>

            <template v-else-if="inspectorTab==='global'">
              <div class="inspector-title"><Palette :size="18"/><div><strong>Identidade visual</strong><small>Configurações globais</small></div></div>
              <label>Cor principal<input type="color" :value="String(globalStyles.primary||'#3151cf')" @input="updateGlobal('primary',($event.target as HTMLInputElement).value)"/></label>
              <label>Cor secundária<input type="color" :value="String(globalStyles.secondary||'#151c31')" @input="updateGlobal('secondary',($event.target as HTMLInputElement).value)"/></label>
              <label>Cor de destaque<input type="color" :value="String(globalStyles.accent||'#6d72ef')" @input="updateGlobal('accent',($event.target as HTMLInputElement).value)"/></label>
              <label>Cor do texto<input type="color" :value="String(globalStyles.text||'#1d273a')" @input="updateGlobal('text',($event.target as HTMLInputElement).value)"/></label>
              <label>Cor de fundo<input type="color" :value="String(globalStyles.background||'#ffffff')" @input="updateGlobal('background',($event.target as HTMLInputElement).value)"/></label>
              <label>Fonte dos títulos<input :value="String(globalStyles.heading_font||'Inter')" @input="updateGlobal('heading_font',($event.target as HTMLInputElement).value)"/></label>
              <label>Fonte dos textos<input :value="String(globalStyles.body_font||'Inter')" @input="updateGlobal('body_font',($event.target as HTMLInputElement).value)"/></label>
              <label>Arredondamento<input type="number" min="0" max="60" :value="Number(globalStyles.radius||16)" @input="updateGlobal('radius',Number(($event.target as HTMLInputElement).value))"/></label>
              <hr/><strong>Compartilhamento</strong>
              <label>Título social<input :value="String(content.seo.title||'')" @input="updateSeo('title',($event.target as HTMLInputElement).value)"/></label>
              <label>Descrição<textarea :value="String(content.seo.description||'')" @input="updateSeo('description',($event.target as HTMLTextAreaElement).value)"></textarea></label>
              <label>Imagem de compartilhamento<input :value="String(content.seo.share_image||'')" placeholder="https://…" @input="updateSeo('share_image',($event.target as HTMLInputElement).value)"/></label>
            </template>

            <template v-else-if="selectedBlock">
              <div class="inspector-title"><Settings2 :size="18"/><div><strong>{{ displayType(selectedBlock.type) }}</strong><small>{{ selectedBlock.id }}</small></div></div>
              <template v-if="inspectorTab==='content'">
                <label v-if="'eyebrow' in selectedBlock.props">Chamada pequena<input :value="String(selectedBlock.props.eyebrow||'')" @input="updateProp('eyebrow',($event.target as HTMLInputElement).value)"/></label>
                <label v-if="'title' in selectedBlock.props">Título<input :value="String(selectedBlock.props.title||'')" @input="updateProp('title',($event.target as HTMLInputElement).value)"/></label>
                <label v-if="'text' in selectedBlock.props">Texto<textarea :value="String(selectedBlock.props.text||'')" @input="updateProp('text',($event.target as HTMLTextAreaElement).value)"></textarea></label>
                <label v-if="'subtitle' in selectedBlock.props">Subtítulo<textarea :value="String(selectedBlock.props.subtitle||'')" @input="updateProp('subtitle',($event.target as HTMLTextAreaElement).value)"></textarea></label>
                <label v-if="'label' in selectedBlock.props">Rótulo<input :value="String(selectedBlock.props.label||'')" @input="updateProp('label',($event.target as HTMLInputElement).value)"/></label>
                <label v-if="'cta' in selectedBlock.props">Texto do botão<input :value="String(selectedBlock.props.cta||'')" @input="updateProp('cta',($event.target as HTMLInputElement).value)"/></label>
                <label v-if="'button' in selectedBlock.props">Texto do botão<input :value="String(selectedBlock.props.button||'')" @input="updateProp('button',($event.target as HTMLInputElement).value)"/></label>
                <label v-if="'image' in selectedBlock.props">Imagem<input :value="String(selectedBlock.props.image||'')" placeholder="https://…" @input="updateProp('image',($event.target as HTMLInputElement).value)"/></label>
                <label v-if="'url' in selectedBlock.props">Link<input :value="String(selectedBlock.props.url||'')" placeholder="https://…" @input="updateProp('url',($event.target as HTMLInputElement).value)"/></label>
                <label v-if="'phone' in selectedBlock.props">Telefone<input :value="String(selectedBlock.props.phone||'')" @input="updateProp('phone',($event.target as HTMLInputElement).value)"/></label>
                <label v-if="'email' in selectedBlock.props">E-mail<input :value="String(selectedBlock.props.email||'')" @input="updateProp('email',($event.target as HTMLInputElement).value)"/></label>
                <label v-if="'address' in selectedBlock.props">Endereço<textarea :value="String(selectedBlock.props.address||'')" @input="updateProp('address',($event.target as HTMLTextAreaElement).value)"></textarea></label>
                <div class="inspector-actions">
                  <button @click="copyBlock(selectedBlock)"><Copy :size="15"/> Copiar</button>
                  <button @click="duplicateBlock(selectedBlock)"><Clipboard :size="15"/> Duplicar</button>
                  <button v-if="clipboard" @click="pasteBlock"><Plus :size="15"/> Colar</button>
                  <button class="danger" @click="removeBlock(selectedBlock)"><Trash2 :size="15"/> Excluir</button>
                </div>
              </template>

              <template v-else-if="inspectorTab==='style'">
                <label>Fonte<input :value="String(selectedBlock.style.fontFamily||'')" placeholder="Herdar global" @input="updateStyle('fontFamily',($event.target as HTMLInputElement).value)"/></label>
                <label>Tamanho<input type="number" :value="Number(String(selectedBlock.style.fontSize||'0').replace('px',''))" @input="updateStyle('fontSize',`${($event.target as HTMLInputElement).value}px`)"/></label>
                <label>Peso<select :value="String(selectedBlock.style.fontWeight||'')" @change="updateStyle('fontWeight',($event.target as HTMLSelectElement).value)"><option value="">Herdar</option><option value="400">Regular</option><option value="500">Médio</option><option value="600">Semibold</option><option value="700">Bold</option><option value="800">Extra bold</option></select></label>
                <label>Alinhamento<select :value="String(selectedBlock.style.textAlign||'')" @change="updateStyle('textAlign',($event.target as HTMLSelectElement).value)"><option value="">Padrão</option><option value="left">Esquerda</option><option value="center">Centro</option><option value="right">Direita</option></select></label>
                <label>Cor do texto<input type="color" :value="String(selectedBlock.style.color||globalStyles.text||'#1d273a')" @input="updateStyle('color',($event.target as HTMLInputElement).value)"/></label>
                <label>Fundo<input type="color" :value="String(selectedBlock.style.backgroundColor||'#ffffff')" @input="updateStyle('backgroundColor',($event.target as HTMLInputElement).value)"/></label>
                <label>Raio<input type="number" min="0" max="80" :value="Number(String(selectedBlock.style.borderRadius||'0').replace('px',''))" @input="updateStyle('borderRadius',`${($event.target as HTMLInputElement).value}px`)"/></label>
                <label>Padding<input :value="String(selectedBlock.style.padding||'')" placeholder="24px" @input="updateStyle('padding',($event.target as HTMLInputElement).value)"/></label>
                <label>Margin<input :value="String(selectedBlock.style.margin||'')" placeholder="0 auto" @input="updateStyle('margin',($event.target as HTMLInputElement).value)"/></label>
                <label>Gap<input :value="String(selectedBlock.style.gap||'')" placeholder="16px" @input="updateStyle('gap',($event.target as HTMLInputElement).value)"/></label>
                <label>Largura máxima<input :value="String(selectedBlock.style.maxWidth||'')" placeholder="1180px" @input="updateStyle('maxWidth',($event.target as HTMLInputElement).value)"/></label>
                <label>Opacidade<input type="number" min="0" max="1" step="0.05" :value="Number(selectedBlock.style.opacity??1)" @input="updateStyle('opacity',Number(($event.target as HTMLInputElement).value))"/></label>
              </template>

              <template v-else>
                <div class="responsive-summary"><strong>{{ device==='desktop'?'Desktop':device==='tablet'?'Tablet':'Mobile' }}</strong><span>Valores específicos substituem o estilo global do bloco.</span></div>
                <label>Tamanho do título/texto<input type="number" min="8" max="120" :value="Number(String(selectedBlock.responsive[device].fontSize||'0').replace('px',''))" @input="updateResponsive('fontSize',`${($event.target as HTMLInputElement).value}px`)"/></label>
                <label>Padding<input :value="String(selectedBlock.responsive[device].padding||'')" placeholder="Ex.: 20px" @input="updateResponsive('padding',($event.target as HTMLInputElement).value)"/></label>
                <label>Gap<input :value="String(selectedBlock.responsive[device].gap||'')" placeholder="Ex.: 12px" @input="updateResponsive('gap',($event.target as HTMLInputElement).value)"/></label>
                <div class="hide-grid">
                  <button :class="{active:selectedBlock.responsive.hidden.desktop}" @click="toggleHidden('desktop')"><Monitor :size="15"/> Ocultar desktop</button>
                  <button :class="{active:selectedBlock.responsive.hidden.tablet}" @click="toggleHidden('tablet')"><Tablet :size="15"/> Ocultar tablet</button>
                  <button :class="{active:selectedBlock.responsive.hidden.mobile}" @click="toggleHidden('mobile')"><Smartphone :size="15"/> Ocultar mobile</button>
                </div>
              </template>
            </template>

            <div v-else class="empty-side">Selecione um bloco no canvas ou na estrutura.</div>
          </div>
        </aside>
      </div>
    </section>
  </Teleport>
</template>

<style scoped>
.page-editor{position:fixed;inset:0;z-index:10000;display:grid;grid-template-rows:auto auto 1fr;background:#eef1f6;color:#172033;font-family:Inter,system-ui,sans-serif}.editor-topbar{display:grid;grid-template-columns:minmax(190px,1fr) auto minmax(270px,1fr);align-items:center;gap:14px;padding:10px 14px;background:#111a30;color:#fff}.editor-brand{display:flex;align-items:center;gap:9px}.editor-brand div{display:grid}.editor-brand small{color:#aab6ce}.device-switcher,.top-actions{display:flex;gap:6px;align-items:center}.device-switcher button,.top-actions button,.icon{min-height:38px;border:1px solid rgba(255,255,255,.16);border-radius:9px;background:rgba(255,255,255,.06);color:#fff;padding:0 10px;display:inline-flex;align-items:center;justify-content:center;gap:6px;font:inherit;cursor:pointer}.device-switcher button.active{background:#fff;color:#172033}.top-actions{justify-content:flex-end}.top-actions .publish{background:#4164e8;border-color:#4164e8}.mobile-panel{display:none!important}.editor-alert{margin:0;padding:9px 14px;font-size:.9rem}.editor-alert.error{background:#fff0f0;color:#a62323}.editor-alert.success{background:#e9f8ef;color:#176a3b}.editor-body{min-height:0;display:grid;grid-template-columns:270px minmax(0,1fr) 320px}.editor-left,.editor-right{min-height:0;overflow:hidden;background:#fff;border-right:1px solid #dce2eb}.editor-right{border-right:0;border-left:1px solid #dce2eb}.side-tabs,.inspector-tabs{display:flex;gap:4px;padding:8px;border-bottom:1px solid #e4e8ef;overflow:auto}.side-tabs button,.inspector-tabs button{border:0;border-radius:8px;background:transparent;padding:8px;font:inherit;font-size:.78rem;font-weight:750;display:flex;align-items:center;gap:5px;white-space:nowrap;cursor:pointer}.side-tabs button.active,.inspector-tabs button.active{background:#eaf0ff;color:#2946ae}.element-list{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:10px;overflow:auto;max-height:calc(100dvh - 130px)}.element-list button{min-height:48px;border:1px solid #e0e5ee;border-radius:9px;background:#fff;display:flex;align-items:center;gap:7px;padding:8px;text-align:left;cursor:pointer}.structure-list,.template-list{display:grid;gap:7px;padding:10px;overflow:auto;max-height:calc(100dvh - 130px)}.structure-item{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:7px;padding:9px;border:1px solid #e1e6ee;border-radius:9px;cursor:pointer}.structure-item.selected{border-color:#4164e8;background:#f3f6ff}.structure-item div{min-width:0;display:grid}.structure-item small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#788296}.mini-actions{display:flex!important;grid-auto-flow:column}.mini-actions button{border:0;background:#eef1f6;border-radius:6px;padding:4px;cursor:pointer}.template-list button{display:grid;gap:5px;border:1px solid #dfe5ee;border-radius:11px;background:#fff;padding:12px;text-align:left;cursor:pointer}.template-list span,.template-list small{color:#697489}.editor-stage{min-width:0;min-height:0;overflow:auto;padding:30px;background:radial-gradient(circle at 1px 1px,#ccd3df 1px,transparent 0);background-size:18px 18px}.canvas-frame{max-width:100%;min-height:100%;margin:0 auto;transition:width .2s}.canvas-page{min-height:720px;background:var(--preview-bg);color:var(--preview-text);box-shadow:0 14px 50px rgba(20,31,54,.16);overflow:hidden}.canvas-empty{min-height:500px;display:grid;place-items:center;align-content:center;gap:9px;text-align:center;color:#718097}.canvas-empty button{border:0;border-radius:9px;background:#4164e8;color:#fff;padding:10px 14px}.canvas-block{position:relative;min-height:72px;padding:28px;border:2px solid transparent;box-sizing:border-box}.canvas-block:hover{outline:1px dashed #91a0b7;outline-offset:-3px}.canvas-block.selected{border-color:#4164e8}.canvas-block.hero{padding:60px 36px;background:#172441;color:#fff}.canvas-block.hero h1{font-size:clamp(2rem,6vw,4rem);max-width:700px}.canvas-block button{border:0;border-radius:9px;background:var(--preview-primary);color:#fff;padding:10px 14px}.block-toolbar{position:absolute;z-index:2;top:0;right:0;display:flex;align-items:center;gap:3px;background:#4164e8;color:#fff;padding:4px 6px;border-radius:0 0 0 8px}.block-toolbar button{padding:4px;background:transparent}.image-placeholder{min-height:180px;display:grid;place-items:center;background:#eef1f5;border:1px dashed #aeb9ca}.fake-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.fake-grid i{aspect-ratio:1;background:#e8edf5;border-radius:7px}.fake-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.fake-cards i{padding:18px;background:#f0f3f8;border-radius:8px;font-style:normal}.booking-preview{display:flex;gap:7px;flex-wrap:wrap}.booking-preview span{padding:10px 16px;border:1px solid #d8deea;border-radius:8px}.block-hint{font-size:.75rem;color:#8791a3}.editor-loading{display:grid;place-items:center;min-height:400px}.inspector-scroll{height:calc(100dvh - 110px);overflow:auto;padding:14px;box-sizing:border-box}.inspector-title{display:flex;gap:8px;align-items:center;margin-bottom:15px}.inspector-title div{display:grid}.inspector-title small{color:#7b8699}.inspector-scroll label{display:grid;gap:6px;margin-bottom:12px;font-size:.82rem;font-weight:750}.inspector-scroll input,.inspector-scroll textarea,.inspector-scroll select{box-sizing:border-box;width:100%;border:1px solid #d3dae5;border-radius:8px;padding:9px;font:inherit}.inspector-scroll textarea{min-height:80px;resize:vertical}.inspector-scroll hr{border:0;border-top:1px solid #e3e7ed;margin:16px 0}.inspector-actions,.hide-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:12px}.inspector-actions button,.hide-grid button{min-height:38px;border:1px solid #d7dee9;border-radius:8px;background:#fff;display:flex;align-items:center;justify-content:center;gap:5px;cursor:pointer}.inspector-actions .danger{color:#aa2525}.hide-grid button.active{background:#fff0f0;color:#a62323;border-color:#efcaca}.responsive-summary{display:grid;gap:4px;margin-bottom:14px;padding:11px;background:#f2f5fb;border-radius:9px}.responsive-summary span{font-size:.8rem;color:#758095}.history-list{display:grid;gap:7px}.history-list button{display:flex;justify-content:space-between;gap:8px;align-items:center;border:1px solid #e0e5ee;border-radius:9px;background:#fff;padding:10px;text-align:left;cursor:pointer}.history-list button div{display:grid}.history-list span,.history-list small{color:#798497}.history-list em{font-size:.72rem;font-style:normal;color:#4164e8}.empty-side{padding:22px;text-align:center;color:#7d8798}.desktop-label{display:inline}.sp-public-editor-open{overflow:hidden}
@media(max-width:900px){.editor-topbar{grid-template-columns:1fr auto}.device-switcher{display:none}.editor-brand{display:none}.editor-body{grid-template-columns:1fr}.editor-left,.editor-right{position:fixed;z-index:10002;top:58px;bottom:0;width:min(88vw,330px);transform:translateX(-110%);transition:transform .2s;box-shadow:15px 0 50px rgba(15,25,45,.2)}.editor-right{right:0;left:auto;transform:translateX(110%)}.editor-left.open,.editor-right.open{transform:translateX(0)}.editor-stage{padding:16px}.mobile-panel{display:inline-flex!important}.desktop-label{display:none}.top-actions{grid-column:1/-1;justify-content:center}.editor-topbar{gap:6px}.canvas-page{min-height:650px}.inspector-scroll{height:calc(100dvh - 120px)}}
@media(max-width:560px){.top-actions .soft:nth-of-type(2){display:none}.editor-stage{padding:8px}.canvas-block{padding:20px}.canvas-block.hero{padding:42px 20px}.fake-cards{grid-template-columns:1fr}.element-list{grid-template-columns:1fr 1fr}}
</style>
