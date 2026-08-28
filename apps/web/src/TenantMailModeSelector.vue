<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Building2, MailCheck, RefreshCw, ServerCog } from 'lucide-vue-next'

type SmtpStatus = {
  enabled:boolean;delivery_mode?:'platform'|'tenant';configured:boolean;tenant_configured?:boolean;platform_available?:boolean;
  platform_sender?:string|null;host:string;port:number;username:string;from_email:string;from_name:string;reply_to:string;
  use_tls:boolean;use_ssl:boolean;timeout_seconds:number;password_configured:boolean
}
type Envelope<T>={data:T;error?:{message?:string}}

const visible=ref(false)
const status=ref<SmtpStatus|null>(null)
const loading=ref(false)
const error=ref('')
const message=ref('')
const mode=computed(()=>status.value?.delivery_mode||'tenant')
let requestGeneration=0
let routeRaf=0

function token():string{return localStorage.getItem('scheduler_pro_access_token')||''}
async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await fetch(`/api/v1${path}`,{...init,cache:'no-store',headers:{accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),authorization:`Bearer ${token()}`,...(init.headers||{})}})
  const payload=await response.json().catch(()=>({})) as Partial<Envelope<T>>
  if(!response.ok)throw new Error(payload.error?.message||`Não foi possível concluir a operação (${response.status}).`)
  return payload.data as T
}

async function load(force=false):Promise<void>{
  if(loading.value)return
  if((status.value&&!force)||!visible.value)return
  const generation=++requestGeneration
  loading.value=true;error.value=''
  try{const data=await api<SmtpStatus>('/notifications/smtp');if(generation===requestGeneration)status.value=data}
  catch(exc){if(generation===requestGeneration)error.value=exc instanceof Error?exc.message:'Falha ao consultar o canal de e-mail.'}
  finally{if(generation===requestGeneration)loading.value=false}
}

async function choose(value:'platform'|'tenant'):Promise<void>{
  if(!status.value||loading.value)return
  loading.value=true;error.value='';message.value=''
  try{
    status.value=await api<SmtpStatus>('/notifications/smtp',{method:'PUT',body:JSON.stringify({delivery_mode:value,enabled:value==='platform'?true:status.value.enabled})})
    message.value=value==='platform'?'Os e-mails da agenda usarão a conta compartilhada da plataforma.':'Os e-mails da agenda usarão a conta SMTP própria configurada nesta tela.'
  }catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível alterar o modo de envio.'}
  finally{loading.value=false}
}

function syncFromRoute():void{
  const next=(window.location.hash||'').replace(/^#/,'')==='smtp'
  if(next===visible.value){if(next&&!status.value&&!loading.value)void load();return}
  visible.value=next
  requestGeneration+=1
  if(!next){status.value=null;loading.value=false;error.value='';message.value='';return}
  void load()
}

function scheduleRouteSync():void{cancelAnimationFrame(routeRaf);routeRaf=requestAnimationFrame(syncFromRoute)}

onMounted(()=>{
  window.addEventListener('hashchange',scheduleRouteSync)
  window.addEventListener('popstate',scheduleRouteSync)
  scheduleRouteSync()
})
onUnmounted(()=>{
  window.removeEventListener('hashchange',scheduleRouteSync)
  window.removeEventListener('popstate',scheduleRouteSync)
  cancelAnimationFrame(routeRaf);requestGeneration+=1
})
</script>

<template>
  <Teleport v-if="visible" to=".tenant-console .main-content > .sp-extension-root">
    <section class="sp-mail-mode-card">
      <header><div><span>Canal de e-mail</span><strong>Como esta empresa vai enviar e-mails?</strong><small>Escolha uma única origem. Nada fica sobreposto à tela de SMTP.</small></div><button type="button" :disabled="loading" title="Atualizar" @click="load(true)"><RefreshCw :class="{spin:loading}" :size="17"/></button></header>
      <div class="sp-mail-mode-options">
        <button :class="{active:mode==='platform'}" :disabled="loading||status?.platform_available===false" @click="choose('platform')"><Building2 :size="20"/><span><strong>Usar e-mail da plataforma</strong><small v-if="status?.platform_available">Conta compartilhada pronta{{ status.platform_sender ? ` · ${status.platform_sender}` : '' }}</small><small v-else>Indisponível até o administrador configurar o SMTP da plataforma.</small></span><MailCheck v-if="mode==='platform'" :size="18"/></button>
        <button :class="{active:mode==='tenant'}" :disabled="loading" @click="choose('tenant')"><ServerCog :size="20"/><span><strong>Usar minha conta SMTP</strong><small>{{ status?.tenant_configured ? 'Conta própria já configurada.' : 'Configure servidor, usuário, senha e remetente abaixo.' }}</small></span><MailCheck v-if="mode==='tenant'" :size="18"/></button>
      </div>
      <p v-if="message" class="ok">{{message}}</p><p v-if="error" class="bad">{{error}}</p>
    </section>
  </Teleport>
</template>

<style>
.sp-mail-mode-card{order:-2;box-sizing:border-box;width:100%;margin:0 0 16px;padding:16px 18px;border:1px solid #dbe4ef;border-radius:18px;background:linear-gradient(135deg,#f8fbff,#f7f7ff);box-shadow:0 10px 30px rgba(15,23,42,.055);color:#14243b}.sp-mail-mode-card header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:12px}.sp-mail-mode-card header span,.sp-mail-mode-card header strong,.sp-mail-mode-card header small{display:block}.sp-mail-mode-card header span{font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:.08em;color:#2563eb}.sp-mail-mode-card header strong{margin-top:3px;font-size:14px}.sp-mail-mode-card header small{margin-top:4px;color:#758499;font-size:10px}.sp-mail-mode-card header>button{width:36px;height:36px;border:1px solid #dce5f0;border-radius:10px;background:#fff;color:#355172;display:grid;place-items:center}.sp-mail-mode-options{display:grid;grid-template-columns:1fr 1fr;gap:10px}.sp-mail-mode-options>button{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;min-height:78px;padding:12px;border:1px solid #dce5f0;border-radius:13px;background:#fff;color:#34455e;text-align:left;font:inherit;cursor:pointer}.sp-mail-mode-options>button.active{border-color:#2563eb;background:#eff6ff;box-shadow:0 0 0 3px rgba(37,99,235,.08)}.sp-mail-mode-options>button:disabled{opacity:.55;cursor:not-allowed}.sp-mail-mode-options strong,.sp-mail-mode-options small{display:block}.sp-mail-mode-options strong{font-size:12px}.sp-mail-mode-options small{margin-top:4px;color:#758499;font-size:10px;line-height:1.35}.sp-mail-mode-card p{margin:10px 0 0;padding:9px 10px;border-radius:9px;font-size:10px;font-weight:700}.sp-mail-mode-card p.ok{background:#ecfdf5;color:#047857}.sp-mail-mode-card p.bad{background:#fff1f2;color:#be123c}.spin{animation:spmailspin 1s linear infinite}@keyframes spmailspin{to{transform:rotate(360deg)}}@media(max-width:700px){.sp-mail-mode-card{padding:13px;border-radius:15px}.sp-mail-mode-options{grid-template-columns:1fr}.sp-mail-mode-options>button{min-height:68px}}
</style>
