export const TEMPLATE_RUNTIME_SDK_VERSION='1.0.0';
function required(adapter,name){const fn=adapter?.[name];if(typeof fn!=='function') throw new Error(`Host adapter não implementa ${name}().`);return fn.bind(adapter);}
function optional(adapter,name,fallback){const fn=adapter?.[name];return typeof fn==='function'?fn.bind(adapter):fallback;}
export function createTemplateRuntimeSdk(adapter={}){
  const context=required(adapter,'getContext');
  const branding=optional(adapter,'getBranding',async()=>({}));
  const features=optional(adapter,'getFeatures',async()=>({}));
  const navigate=optional(adapter,'navigate',async({to})=>{if(globalThis.location&&to)globalThis.location.href=to;return{to};});
  const track=optional(adapter,'track',async()=>({accepted:false}));
  return Object.freeze({
    version:TEMPLATE_RUNTIME_SDK_VERSION,
    context:{get:()=>context()},
    branding:{get:()=>branding()},
    features:{get:()=>features()},
    booking:{
      catalog:(input={})=>required(adapter,'bookingCatalog')(input),
      availability:(input={})=>required(adapter,'bookingAvailability')(input),
      create:(input={})=>required(adapter,'bookingCreate')(input),
      cancel:(input={})=>optional(adapter,'bookingCancel',async()=>{throw new Error('Cancelamento não disponível neste host.');})(input),
      reschedule:(input={})=>optional(adapter,'bookingReschedule',async()=>{throw new Error('Reagendamento não disponível neste host.');})(input),
    },
    navigation:{
      open:(to,options={})=>navigate({to,...options}),
      openLanding:(options={})=>navigate({to:'/pagina',...options}),
      openBooking:(options={})=>navigate({to:'/agendar',...options}),
      openLogin:(options={})=>navigate({to:'/login',...options}),
    },
    analytics:{track:(event,properties={})=>track({event:String(event),properties})},
  });
}
export function installTemplateRuntimeGlobal(adapter,globalName='ARGWSRuntime'){
  const sdk=createTemplateRuntimeSdk(adapter); globalThis[globalName]=sdk; return sdk;
}
