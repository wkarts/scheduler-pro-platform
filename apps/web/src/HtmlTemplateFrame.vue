<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

type Mode='landing'|'booking'|'preview'
type ApiBridgeRequest={
  type:'scheduler-pro-html-api-request'
  id:string
  path:string
  method:string
  body?:string|null
}
type HeightMessage={type:'scheduler-pro-html-height';height:number}

const props=withDefaults(defineProps<{html:string;mode?:Mode}>(),{mode:'landing'})
const frame=ref<HTMLIFrameElement|null>(null)
const frameHeight=ref(720)

const BRIDGE_SOURCE=`
(function(){
  var pending=new Map();
  var sequence=0;
  function publicPath(raw){
    var value=String(raw||'');
    var marker='/api/v1/public';
    var index=value.indexOf(marker);
    return index>=0?value.slice(index):'';
  }
  window.fetch=function(input,init){
    init=init||{};
    var raw=typeof input==='string'?input:(input&&input.url?input.url:'');
    var path=publicPath(raw);
    if(!path){return Promise.reject(new Error('Acesso de rede externo bloqueado pelo Scheduler Pro.'));}
    var id='sp-html-'+(++sequence)+'-'+Date.now();
    return new Promise(function(resolve,reject){
      pending.set(id,{resolve:resolve,reject:reject});
      parent.postMessage({
        type:'scheduler-pro-html-api-request',id:id,path:path,
        method:String(init.method||'GET').toUpperCase(),
        body:typeof init.body==='string'?init.body:null
      },'*');
      setTimeout(function(){
        if(!pending.has(id))return;
        pending.delete(id);
        reject(new Error('Tempo esgotado ao consultar o Scheduler Pro.'));
      },30000);
    });
  };
  window.addEventListener('message',function(event){
    if(event.source!==parent)return;
    var data=event.data||{};
    if(data.type!=='scheduler-pro-html-api-response'||!data.id)return;
    var entry=pending.get(data.id);
    if(!entry)return;
    pending.delete(data.id);
    entry.resolve(new Response(String(data.body||''),{
      status:Number(data.status||500),
      headers:data.headers||{'content-type':'application/json'}
    }));
  });
  function reportHeight(){
    var root=document.documentElement;
    var body=document.body;
    var height=Math.max(root?root.scrollHeight:0,body?body.scrollHeight:0,480);
    parent.postMessage({type:'scheduler-pro-html-height',height:height},'*');
  }
  window.addEventListener('load',reportHeight);
  window.addEventListener('resize',reportHeight);
  if(window.ResizeObserver){new ResizeObserver(reportHeight).observe(document.documentElement);}
  setTimeout(reportHeight,80);setTimeout(reportHeight,500);setTimeout(reportHeight,1500);
})();
`

const csp=`<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob: https:; style-src 'unsafe-inline' https:; font-src data: https:; script-src 'unsafe-inline'; media-src data: blob: https:; frame-src https:; connect-src 'none'; form-action 'none'; base-uri 'none'">`
const bridge=`<script>${BRIDGE_SOURCE.replace(/<\\/script/gi,'<\\\\/script')}<\/script>`

const srcdoc=computed(()=>{
  const source=props.html||''
  const injection=`${csp}${bridge}`
  if(/<head(?:\s[^>]*)?>/i.test(source))return source.replace(/<head(\s[^>]*)?>/i,(match)=>`${match}${injection}`)
  if(/<html(?:\s[^>]*)?>/i.test(source))return source.replace(/<html(\s[^>]*)?>/i,(match)=>`${match}<head>${injection}</head>`)
  return `<!doctype html><html><head>${injection}</head><body>${source}</body></html>`
})

function allowed(path:string,method:string):boolean{
  const clean=path.split('#',1)[0]||''
  if(method==='GET'&&clean.startsWith('/api/v1/public/booking/availability'))return true
  if(clean==='/api/v1/public/booking'&&['GET','POST'].includes(method))return true
  if(method==='GET'&&clean.startsWith('/api/v1/public/landing'))return true
  return false
}

async function handleApiRequest(data:ApiBridgeRequest):Promise<void>{
  const target=frame.value?.contentWindow
  if(!target)return
  const method=String(data.method||'GET').toUpperCase()
  if(!allowed(data.path,method)){
    target.postMessage({type:'scheduler-pro-html-api-response',id:data.id,status:403,body:JSON.stringify({error:{code:'HTML_TEMPLATE_API_DENIED',message:'Recurso não permitido neste modelo.',details:{}}}),headers:{'content-type':'application/json'}},'*')
    return
  }
  try{
    const response=await fetch(data.path,{method,cache:'no-store',headers:{Accept:'application/json',...(data.body?{'content-type':'application/json'}:{})},...(data.body?{body:data.body}:{})})
    const body=await response.text()
    target.postMessage({type:'scheduler-pro-html-api-response',id:data.id,status:response.status,body,headers:{'content-type':response.headers.get('content-type')||'application/json'}},'*')
  }catch{
    target.postMessage({type:'scheduler-pro-html-api-response',id:data.id,status:503,body:JSON.stringify({error:{code:'HTML_TEMPLATE_API_UNAVAILABLE',message:'Não foi possível acessar o Scheduler Pro.',details:{}}}),headers:{'content-type':'application/json'}},'*')
  }
}

function onMessage(event:MessageEvent):void{
  if(event.source!==frame.value?.contentWindow)return
  const data=event.data as Partial<ApiBridgeRequest&HeightMessage>|null
  if(!data||typeof data!=='object')return
  if(data.type==='scheduler-pro-html-api-request'&&typeof data.id==='string'&&typeof data.path==='string')void handleApiRequest(data as ApiBridgeRequest)
  if(data.type==='scheduler-pro-html-height'){
    const next=Math.max(480,Math.min(20000,Number(data.height||0)))
    if(Number.isFinite(next))frameHeight.value=next
  }
}

onMounted(()=>window.addEventListener('message',onMessage))
onUnmounted(()=>window.removeEventListener('message',onMessage))
</script>

<template>
  <iframe
    ref="frame"
    class="scheduler-html-template-frame"
    :data-mode="mode"
    :srcdoc="srcdoc"
    :style="{height:`${frameHeight}px`}"
    sandbox="allow-scripts allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
    referrerpolicy="no-referrer"
    title="Página personalizada"
  />
</template>

<style scoped>
.scheduler-html-template-frame{display:block;width:100%;min-height:480px;border:0;background:transparent;overflow:hidden}
</style>
