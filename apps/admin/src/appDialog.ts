export type AppDialogOptions={
  title?:string
  message:string
  confirmLabel?:string
  cancelLabel?:string
  danger?:boolean
}

export type AppPromptOptions=AppDialogOptions&{
  value?:string
  placeholder?:string
  inputLabel?:string
}

type DialogMode='alert'|'confirm'|'prompt'

type DialogResult=boolean|string|null

function escapeHtml(value:string):string{
  return value.replace(/[&<>"']/g,char=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;',
  }[char]||char))
}

function openDialog(
  mode:DialogMode,
  options:AppDialogOptions|AppPromptOptions,
):Promise<DialogResult>{
  return new Promise(resolve=>{
    document.getElementById('scheduler-pro-app-dialog')?.remove()
    const overlay=document.createElement('div')
    overlay.id='scheduler-pro-app-dialog'
    overlay.style.cssText='position:fixed;inset:0;z-index:2147483000;display:grid;place-items:center;padding:18px;background:rgba(15,23,42,.5);backdrop-filter:blur(7px)'
    const prompt=options as AppPromptOptions
    const input=mode==='prompt'?`<label style="display:grid;gap:6px;margin:0 0 18px;color:#52647c;font-size:12px;font-weight:700">${escapeHtml(prompt.inputLabel||'Valor')}<input data-sp-dialog-input value="${escapeHtml(prompt.value||'')}" placeholder="${escapeHtml(prompt.placeholder||'')}" style="min-height:42px;border:1px solid #cfdbea;border-radius:10px;padding:0 11px;font:inherit;color:#12213a;outline:none"></label>`:''
    const cancel=mode==='alert'?'':`<button data-sp-dialog-cancel style="min-height:40px;border:1px solid #d8e2ee;border-radius:10px;background:#fff;color:#203650;padding:0 14px;font-weight:700;cursor:pointer">${escapeHtml(options.cancelLabel||'Cancelar')}</button>`
    overlay.innerHTML=`<section role="dialog" aria-modal="true" aria-labelledby="sp-dialog-title" style="width:min(470px,100%);padding:20px;border:1px solid #d8e2ee;border-radius:18px;background:#fff;color:#12213a;box-shadow:0 28px 90px rgba(15,23,42,.3);font-family:Inter,system-ui,sans-serif"><h2 id="sp-dialog-title" style="margin:0;font-size:20px">${escapeHtml(options.title||(mode==='alert'?'Aviso':'Confirmação'))}</h2><p style="margin:9px 0 18px;color:#5b6b82;font-size:13px;line-height:1.55">${escapeHtml(options.message)}</p>${input}<div style="display:flex;justify-content:flex-end;gap:9px">${cancel}<button data-sp-dialog-confirm style="min-height:40px;border:1px solid ${options.danger?'#b4232e':'#2563eb'};border-radius:10px;background:${options.danger?'#b4232e':'#2563eb'};color:#fff;padding:0 14px;font-weight:800;cursor:pointer">${escapeHtml(options.confirmLabel||(mode==='alert'?'OK':'Confirmar'))}</button></div></section>`
    const field=overlay.querySelector<HTMLInputElement>('[data-sp-dialog-input]')
    const finish=(confirmed:boolean)=>{
      const result:DialogResult=mode==='prompt'?(confirmed?field?.value??'':null):confirmed
      overlay.remove()
      resolve(result)
    }
    overlay.addEventListener('click',event=>{
      const target=event.target as HTMLElement
      if(target===overlay||target.closest('[data-sp-dialog-cancel]'))finish(false)
      else if(target.closest('[data-sp-dialog-confirm]'))finish(true)
    })
    overlay.addEventListener('keydown',event=>{
      if(event.key==='Escape')finish(false)
      if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();finish(true)}
    })
    document.body.appendChild(overlay)
    ;(field||overlay.querySelector<HTMLButtonElement>('[data-sp-dialog-confirm]'))?.focus()
  })
}

export async function confirmDialog(options:AppDialogOptions|string):Promise<boolean>{
  const config:AppDialogOptions=typeof options==='string'?{message:options}:options
  return Boolean(await openDialog('confirm',config))
}

export async function alertDialog(options:AppDialogOptions|string):Promise<void>{
  const config:AppDialogOptions=typeof options==='string'?{message:options}:options
  await openDialog('alert',config)
}

export async function promptDialog(options:AppPromptOptions):Promise<string|null>{
  const result=await openDialog('prompt',options)
  return typeof result==='string'?result:null
}
