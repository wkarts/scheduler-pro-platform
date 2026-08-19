<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Building2, MailCheck, RefreshCw, ServerCog } from 'lucide-vue-next'

type SmtpStatus = {
  enabled:boolean
  delivery_mode?:'platform'|'tenant'
  configured:boolean
  tenant_configured?:boolean
  platform_available?:boolean
  platform_sender?:string|null
  host:string
  port:number
  username:string
  from_email:string
  from_name:string
  reply_to:string
  use_tls:boolean
  use_ssl:boolean
  timeout_seconds:number
  password_configured:boolean
}
type Envelope<T>={data:T;error?:{message?:string}}

const visible=ref(false)
const status=ref<SmtpStatus|null>(null)
const loading=ref(false)
const error=ref('')
const message=ref('')
const mode=computed(()=>status.value?.delivery_mode||'tenant')

function token():string{return localStorage.getItem('scheduler_pro_access_token')||''}
async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await fetch(`/api/v1${path}`,{...init,headers:{accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),authorization:`Bearer ${token()}`,...(init.headers||{})}})
  const payload=await response.json().catch(()=>({})) as Partial<Envelope<T>>
  if(!response.ok)throw new Error(payload.error?.message||`Não foi possível concluir a operação (${response.status}).`)
  return payload.data as T
}
async function load():Promise<void>{loading.value=true;error.value='';try{status.value=await api<SmtpStatus>('/notifications/smtp')}catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao consultar o canal de e-mail.'}finally{loading.value=false}}
async function choose(value:'platform'|'tenant'):Promise<void>{
  if(!status.value)return
  loading.value=true;error.value='';message.value=''
  try{
    status.value=await api<SmtpStatus>('/notifications/smtp',{method:'PUT',body:JSON.stringify({delivery_mode:value,enabled:value==='platform'?true:status.value.enabled})})
    message.value=value==='platform'?'Os e-mails da agenda usarão a conta compartilhada da plataforma.':'Os e-mails da agenda usarão a conta SMTP própria configurada abaixo.'
  }catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível alterar o modo de envio.'}finally{loading.value=false}
}
function detect():void{
  visible.value=Array.from(document.querySelectorAll('.sp-extension-header h1')).some((node)=>node.textContent?.trim()==='E-mail da agenda')
  if(visible.value&&!status.value)void load()
}
let observer:MutationObserver|undefined
onMounted(()=>{observer=new MutationObserver(detect);observer.observe(document.body,{subtree:true,childList:true,characterData:true});detect()})
onUnmounted(()=>observer?.disconnect())
</script>

<template>
  <Teleport v-if="visible" to="body">
    <section class="sp-mail-mode-card">
      <header><div><span>Canal de e-mail</span><strong>Como o tenant vai enviar e-mails?</strong></div><RefreshCw v-if="loading" class="spin" :size="17"/></header>
      <div class="sp-mail-mode-options">
        <button :class="{active:mode==='platform'}" :disabled="loading||status?.platform_available===false" @click="choose('platform')"><Building2 :size="20"/><span><strong>Usar e-mail da plataforma</strong><small v-if="status?.platform_available">Conta compartilhada pronta{{ status.platform_sender ? ` · ${status.platform_sender}` : '' }}</small><small v-else>Indisponível até o administrador configurar o SMTP da plataforma.</small></span><MailCheck v-if="mode==='platform'" :size="18"/></button>
        <button :class="{active:mode==='tenant'}" :disabled="loading" @click="choose('tenant')"><ServerCog :size="20"/><span><strong>Usar minha conta SMTP</strong><small>{{ status?.tenant_configured ? 'Conta própria já configurada.' : 'Configure servidor, usuário, senha e remetente nesta tela.' }}</small></span><MailCheck v-if="mode==='tenant'" :size="18"/></button>
      </div>
      <p v-if="message" class="ok">{{message}}</p><p v-if="error" class="bad">{{error}}</p>
    </section>
  </Teleport>
</template>

<style>
.sp-mail-mode-card{position:fixed;z-index:1450;right:24px;bottom:24px;width:min(560px,calc(100vw - 48px));padding:14px;border:1px solid #dbe4ef;border-radius:18px;background:rgba(255,255,255,.98);box-shadow:0 22px 60px rgba(15,23,42,.2);backdrop-filter:blur(12px);color:#14243b}.sp-mail-mode-card header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.sp-mail-mode-card header span,.sp-mail-mode-card header strong{display:block}.sp-mail-mode-card header span{font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:.08em;color:#2563eb}.sp-mail-mode-card header strong{margin-top:3px;font-size:14px}.sp-mail-mode-options{display:grid;grid-template-columns:1fr 1fr;gap:8px}.sp-mail-mode-options button{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:9px;align-items:center;min-height:74px;padding:11px;border:1px solid #dce5f0;border-radius:13px;background:#fff;color:#34455e;text-align:left;font:inherit;cursor:pointer}.sp-mail-mode-options button.active{border-color:#38bdf8;background:#f0faff;box-shadow:0 0 0 3px rgba(56,189,248,.1)}.sp-mail-mode-options button:disabled{opacity:.55;cursor:not-allowed}.sp-mail-mode-options strong,.sp-mail-mode-options small{display:block}.sp-mail-mode-options strong{font-size:11px}.sp-mail-mode-options small{margin-top:4px;color:#758499;font-size:9px;line-height:1.35}.sp-mail-mode-card p{margin:9px 0 0;padding:8px 10px;border-radius:9px;font-size:10px;font-weight:700}.sp-mail-mode-card p.ok{background:#ecfdf5;color:#047857}.sp-mail-mode-card p.bad{background:#fff1f2;color:#be123c}.spin{animation:spmailspin 1s linear infinite}@keyframes spmailspin{to{transform:rotate(360deg)}}@media(max-width:700px){.sp-mail-mode-card{right:12px;bottom:12px;width:calc(100vw - 24px);padding:11px;border-radius:16px}.sp-mail-mode-options{grid-template-columns:1fr}.sp-mail-mode-options button{min-height:64px}}
</style>
