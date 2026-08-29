type AnalyticsConfig={
  ga4_measurement_id?:string
  google_ads_conversion_id?:string
  google_ads_conversion_label?:string
  meta_pixel_id?:string
  gtm_container_id?:string
  tiktok_pixel_id?:string
}

declare global {
  interface Window {
    dataLayer?: unknown[]
    gtag?: (...args: unknown[])=>void
    fbq?: ((...args: unknown[])=>void)&{queue?:unknown[];loaded?:boolean;version?:string}
    ttq?: any
  }
}

const safe=(value:unknown,pattern:RegExp)=>typeof value==='string'&&pattern.test(value.trim())?value.trim():''
function script(id:string,src:string):void{if(document.getElementById(id))return;const node=document.createElement('script');node.id=id;node.async=true;node.src=src;document.head.appendChild(node)}

export function installPublicAnalytics(input:Record<string,unknown>|undefined):AnalyticsConfig{
  const c:AnalyticsConfig={
    ga4_measurement_id:safe(input?.ga4_measurement_id,/^G-[A-Z0-9]+$/i),
    google_ads_conversion_id:safe(input?.google_ads_conversion_id,/^(AW-)?[A-Z0-9-]+$/i),
    google_ads_conversion_label:safe(input?.google_ads_conversion_label,/^[A-Z0-9_-]+$/i),
    meta_pixel_id:safe(input?.meta_pixel_id,/^[0-9]{5,30}$/),
    gtm_container_id:safe(input?.gtm_container_id,/^GTM-[A-Z0-9]+$/i),
    tiktok_pixel_id:safe(input?.tiktok_pixel_id,/^[A-Z0-9]{8,32}$/i),
  }
  if(c.ga4_measurement_id){window.dataLayer=window.dataLayer||[];window.gtag=window.gtag||function(...args:unknown[]){window.dataLayer?.push(args)};window.gtag('js',new Date());window.gtag('config',c.ga4_measurement_id);script('sp-ga4',`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(c.ga4_measurement_id)}`)}
  if(c.google_ads_conversion_id&&!c.ga4_measurement_id){window.dataLayer=window.dataLayer||[];window.gtag=window.gtag||function(...args:unknown[]){window.dataLayer?.push(args)};script('sp-google-ads',`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(c.google_ads_conversion_id)}`)}
  if(c.gtm_container_id){window.dataLayer=window.dataLayer||[];window.dataLayer.push({'gtm.start':Date.now(),event:'gtm.js'});script('sp-gtm',`https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(c.gtm_container_id)}`)}
  if(c.meta_pixel_id&&!window.fbq){const fbq:any=function(...args:unknown[]){fbq.queue.push(args)};fbq.queue=[];fbq.loaded=true;fbq.version='2.0';window.fbq=fbq;script('sp-meta-pixel','https://connect.facebook.net/en_US/fbevents.js');window.fbq('init',c.meta_pixel_id)}
  if(c.tiktok_pixel_id&&!window.ttq){const ttq:any=[];ttq.methods=['page','track'];ttq.setAndDefer=(obj:any,method:string)=>{obj[method]=(...args:unknown[])=>obj.push([method,...args])};ttq.methods.forEach((method:string)=>ttq.setAndDefer(ttq,method));window.ttq=ttq;script('sp-tiktok-pixel','https://analytics.tiktok.com/i18n/pixel/events.js');ttq.load=c.tiktok_pixel_id}
  return c
}

export function trackPublicEvent(name:string,payload:Record<string,unknown>={},config:AnalyticsConfig={}):void{
  const event=String(name||'').trim();if(!event)return
  window.gtag?.('event',event,payload)
  if(event==='booking_completed'&&config.google_ads_conversion_id&&config.google_ads_conversion_label)window.gtag?.('event','conversion',{send_to:`${config.google_ads_conversion_id}/${config.google_ads_conversion_label}`,...payload})
  const metaName=event==='booking_completed'?'Lead':event==='page_view'?'PageView':event
  window.fbq?.('track',metaName,payload)
  window.ttq?.track?.(event,payload)
  window.dataLayer?.push({event,...payload})
}
