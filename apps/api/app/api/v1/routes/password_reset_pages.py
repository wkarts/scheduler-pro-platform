import json
from html import escape

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

router = APIRouter()


def _page(*, token: str, platform_access: bool) -> HTMLResponse:
    endpoint = (
        "/api/v1/auth/platform/password/reset"
        if platform_access
        else "/api/v1/auth/password/reset"
    )
    title = "Scheduler Pro Admin" if platform_access else "Scheduler Pro"
    safe_token = json.dumps(token)
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Redefinir senha — {escape(title)}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,system-ui,Arial,sans-serif;background:#0d1b35;color:#0d1b35;min-height:100vh;display:grid;place-items:center;padding:24px}}main{{width:min(460px,100%);background:#fff;border-radius:18px;padding:34px;box-shadow:0 24px 70px #0005}}h1{{margin:0 0 8px;font-size:28px}}p{{color:#66758f;line-height:1.5}}label{{display:grid;gap:7px;margin:18px 0;font-weight:700;font-size:13px}}input{{width:100%;border:1px solid #cbd7e8;border-radius:10px;padding:13px 14px;font:inherit;outline:none}}input:focus{{border-color:#0b9fea;box-shadow:0 0 0 3px #0b9fea20}}button{{width:100%;border:0;border-radius:10px;padding:13px 16px;font-weight:800;color:white;background:linear-gradient(90deg,#1597ee,#10c8bf);cursor:pointer}}button:disabled{{opacity:.6}}#message{{margin-top:16px;padding:12px;border-radius:9px;display:none}}.ok{{display:block!important;background:#e9fbf3;color:#08784f}}.err{{display:block!important;background:#fff0f0;color:#a51d2d}}</style>
</head>
<body><main><h1>Redefinir senha</h1><p>{escape(title)} · informe uma nova senha com pelo menos 12 caracteres.</p>
<form id="reset-form"><label>Nova senha<input id="password" type="password" minlength="12" autocomplete="new-password" required></label><label>Confirmar nova senha<input id="confirm" type="password" minlength="12" autocomplete="new-password" required></label><button id="submit" type="submit">Salvar nova senha</button></form><div id="message"></div></main>
<script>
const token={safe_token};const endpoint={json.dumps(endpoint)};const form=document.getElementById('reset-form');const message=document.getElementById('message');const submit=document.getElementById('submit');
form.addEventListener('submit',async(e)=>{{e.preventDefault();message.className='';message.style.display='none';const password=document.getElementById('password').value;const confirm=document.getElementById('confirm').value;if(password.length<12){{message.textContent='A senha deve possuir pelo menos 12 caracteres.';message.className='err';return}}if(password!==confirm){{message.textContent='A confirmação da senha não confere.';message.className='err';return}}submit.disabled=true;try{{const response=await fetch(endpoint,{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{token,new_password:password}})}});const body=await response.json().catch(()=>({{}}));if(!response.ok)throw new Error(body?.error?.message||`Falha HTTP ${{response.status}}`);message.textContent='Senha redefinida com sucesso. Você já pode voltar ao aplicativo e entrar com a nova senha.';message.className='ok';form.reset()}}catch(error){{message.textContent=error instanceof Error?error.message:'Não foi possível redefinir a senha.';message.className='err'}}finally{{submit.disabled=false}}}});
</script></body></html>"""
    return HTMLResponse(html, headers={"Cache-Control": "no-store, max-age=0"})


@router.get("/password/reset-page", response_class=HTMLResponse)
async def tenant_reset_page(
    token: str = Query(min_length=32, max_length=1024),
) -> HTMLResponse:
    return _page(token=token, platform_access=False)


@router.get("/platform/password/reset-page", response_class=HTMLResponse)
async def platform_reset_page(
    token: str = Query(min_length=32, max_length=1024),
) -> HTMLResponse:
    return _page(token=token, platform_access=True)
