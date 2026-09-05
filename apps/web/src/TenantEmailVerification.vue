<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { identityEmailToken, clearIdentityEmailToken } from './identity-email-link'
const token=ref(identityEmailToken), password=ref(''), confirmation=ref(''), busy=ref(false), error=ref(''), done=ref(false)
clearIdentityEmailToken()
async function submit():Promise<void>{
  if(busy.value)return
  if(password.value!==confirmation.value){error.value='As senhas não conferem.';return}
  busy.value=true;error.value=''
  try {
    const response=await fetch('/api/v1/access/confirm-email',{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:token.value,new_password:password.value||null})})
    const result=await response.json()
    if(!response.ok)throw new Error(result.error?.message||'Não foi possível confirmar.')
    done.value=true;token.value='';password.value='';confirmation.value=''
  }catch(problem){error.value=problem instanceof Error?problem.message:'Falha temporária. Tente novamente.'}
  finally{busy.value=false}
}
onBeforeUnmount(()=>{token.value='';password.value='';confirmation.value=''})
</script>
<template><main class="identity-confirmation"><form v-if="!done" @submit.prevent="submit"><small>SCHEDULER PRO</small><h1>Confirmar e-mail</h1><p>Em um novo convite, defina sua senha. Para confirmar ou trocar o e-mail de uma conta existente, deixe a senha vazia.</p><label>Nova senha (para aceitar convite)<input v-model="password" type="password" autocomplete="new-password" maxlength="512"/></label><label>Repita a nova senha<input v-model="confirmation" type="password" autocomplete="new-password" maxlength="512"/></label><p v-if="error" role="alert">{{error}}</p><p v-if="!token">Abra novamente o link completo recebido por e-mail.</p><button :disabled="busy||!token">{{busy?'Confirmando…':'Confirmar acesso'}}</button></form><article v-else><h1>E-mail confirmado</h1><p>Entre com seu e-mail e senha. As sessões anteriores foram encerradas por segurança.</p><a href="/login">Ir para o login</a></article></main></template>
<style scoped>.identity-confirmation{min-height:100dvh;display:grid;place-items:center;background:#f4f7fc;padding:24px;box-sizing:border-box}.identity-confirmation form,.identity-confirmation article{width:min(100%,480px);display:grid;gap:18px;background:white;border:1px solid #dae4ef;border-radius:18px;padding:26px;box-sizing:border-box}.identity-confirmation h1{font-size:26px;margin:0}.identity-confirmation p{font-size:14px;line-height:1.6}.identity-confirmation label{display:grid;gap:8px}.identity-confirmation input{width:100%;min-height:46px;border:1px solid #b6c7da;border-radius:10px;padding:10px;box-sizing:border-box;font-size:16px}.identity-confirmation button{background:#26429e;color:#fff;padding:14px;border:0;border-radius:10px;cursor:pointer}.identity-confirmation button:disabled{opacity:.5}.identity-confirmation [role=alert]{color:#a32943}</style>
