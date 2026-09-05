// Runtime regression tests against transpiled production TS; HTTP and storage are test doubles.
const { test, after } = require('node:test')
const assert = require('node:assert/strict')
const { mkdtempSync, rmSync, existsSync } = require('node:fs')
const { tmpdir } = require('node:os')
const path = require('node:path')
const { execFileSync } = require('node:child_process')
const root = path.resolve(__dirname, '../..')
const build = mkdtempSync(path.join(tmpdir(), 'scheduler-auth-test-'))
const localTsc = path.join(root, 'node_modules/typescript/bin/tsc')
const args = ['apps/web/src/tenant-auth-fetch.ts','apps/admin/src/admin-auth-fetch.ts',
  '--target','ES2022','--module','commonjs','--lib','ES2022,DOM,DOM.Iterable','--strict','--outDir',build]
if (existsSync(localTsc)) execFileSync(process.execPath,[localTsc,...args],{cwd:root,stdio:'pipe'})
else execFileSync('tsc',args,{cwd:root,stdio:'pipe'})
after(()=>rmSync(build,{recursive:true,force:true}))
const json = (status,body={}) => new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}})

function setup(role,handler) {
  const store=new Map()
  const events=[]
  global.localStorage={getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)}
  const tenant=role==='tenant'
  const put=(a,r)=>tenant
    ? (store.set('scheduler_pro_access_token',a),store.set('scheduler_pro_refresh_token',r))
    : store.set('scheduler-pro-admin-session',JSON.stringify({accessToken:a,refreshToken:r,userEmail:'test@example.invalid'}))
  const get=()=>tenant?{accessToken:store.get('scheduler_pro_access_token'),refreshToken:store.get('scheduler_pro_refresh_token')}
    : JSON.parse(store.get('scheduler-pro-admin-session')||'{}')
  put('old-access','old-refresh')
  global.window={location:{origin:'https://scheduler.example.invalid'},dispatchEvent:e=>events.push(e.type),
    fetch:async(input,init)=>handler(input instanceof Request?input:new Request(new URL(String(input),window.location.origin),init))}
  const file=path.join(build,tenant?'web/src/tenant-auth-fetch.js':'admin/src/admin-auth-fetch.js')
  delete require.cache[require.resolve(file)]
  const module=require(file)
  module[tenant?'installTenantAuthFetch':'installAdminAuthFetch']()
  const invalidEvent=tenant?'scheduler-pro-realtime-unauthorized':'scheduler-pro-admin-session-invalid'
  return {get,put,events,invalidEvent,fetch:window.fetch}
}

for (const role of ['tenant','admin']) {
  for (const status of [500,502,503,504,429]) {
    test(`${role}: refresh ${status} preserves tokens and returns temporary 503`,async()=>{
      let refreshes=0
      const env=setup(role,async req=>{
        if(req.url.endsWith('/refresh')) {refreshes++;return json(status)}
        return json(401)
      })
      const response=await env.fetch('/api/v1/appointments')
      assert.equal(response.status,503)
      assert.equal(env.get().refreshToken,'old-refresh')
      assert.equal(env.events.includes(env.invalidEvent),false)
      await env.fetch('/api/v1/settings')
      assert.equal(refreshes,1,'cooldown prevents a refresh storm')
    })
  }
  test(`${role}: network error during refresh preserves the session`,async()=>{
    const env=setup(role,async req=>{
      if(req.url.endsWith('/refresh')) throw new TypeError('network unavailable')
      return json(401)
    })
    assert.equal((await env.fetch('/api/v1/appointments')).status,503)
    assert.equal(env.get().refreshToken,'old-refresh')
    assert.equal(env.events.includes(env.invalidEvent),false)
  })
  test(`${role}: malformed successful refresh does not log out`,async()=>{
    const env=setup(role,async req=>json(req.url.endsWith('/refresh')?200:401))
    assert.equal((await env.fetch('/api/v1/appointments')).status,503)
    assert.equal(env.get().refreshToken,'old-refresh')
  })
  test(`${role}: an authoritative refresh 401 invalidates the session`,async()=>{
    const env=setup(role,async()=>json(401))
    assert.equal((await env.fetch('/api/v1/appointments')).status,401)
    assert.equal(env.get().refreshToken,undefined)
    assert.equal(env.events.includes(env.invalidEvent),true)
  })
  test(`${role}: twenty parallel 401s rotate the refresh token only once`,async()=>{
    let refreshes=0
    const env=setup(role,async req=>{
      if(req.url.endsWith('/refresh')) {
        refreshes++
        await new Promise(r=>setTimeout(r,5))
        return json(200,{data:{access_token:'new-access',refresh_token:'new-refresh'}})
      }
      return json(req.headers.get('Authorization')==='Bearer new-access'?200:401,{data:{ok:true}})
    })
    const responses=await Promise.all(Array.from({length:20},(_,i)=>env.fetch(`/api/v1/data?id=${i}`)))
    assert.ok(responses.every(r=>r.status===200))
    assert.equal(refreshes,1)
    assert.equal(env.get().refreshToken,'new-refresh')
  })
  test(`${role}: POST 503 is never automatically replayed`,async()=>{
    let calls=0
    const env=setup(role,async()=>{calls++;return json(503)})
    assert.equal((await env.fetch('/api/v1/appointments',{method:'POST',body:'payload'})).status,503)
    assert.equal(calls,1)
  })
  test(`${role}: POST Request body survives one authorized retry`,async()=>{
    const bodies=[]
    const env=setup(role,async req=>{
      if(req.url.endsWith('/refresh')) return json(200,{data:{access_token:'new-access',refresh_token:'new-refresh'}})
      bodies.push(await req.text())
      return json(req.headers.get('Authorization')==='Bearer new-access'?200:401)
    })
    const request=new Request('https://scheduler.example.invalid/api/v1/appointments',{method:'POST',body:'{"name":"A"}'})
    assert.equal((await env.fetch(request,{headers:{Authorization:'Bearer stale-explicit'}})).status,200)
    assert.deepEqual(bodies,['{"name":"A"}','{"name":"A"}'])
    assert.equal(request.bodyUsed,false)
  })
  test(`${role}: delayed 401 reuses the already rotated access token`,async()=>{
    let refreshes=0
    const env=setup(role,async req=>{
      if(req.url.endsWith('/refresh')) {refreshes++;return json(200,{data:{access_token:'new-access',refresh_token:'new-refresh'}})}
      if(req.headers.get('Authorization')==='Bearer new-access')return json(200)
      if(req.url.includes('slow'))await new Promise(r=>setTimeout(r,15))
      return json(401)
    })
    const responses=await Promise.all([env.fetch('/api/v1/slow'),env.fetch('/api/v1/fast')])
    assert.ok(responses.every(r=>r.status===200))
    assert.equal(refreshes,1)
  })
  test(`${role}: permissions 403 is not a logout or refresh`,async()=>{
    let calls=0
    const env=setup(role,async()=>{calls++;return json(403)})
    assert.equal((await env.fetch('/api/v1/restricted')).status,403)
    assert.equal(calls,1)
    assert.equal(env.get().refreshToken,'old-refresh')
    assert.equal(env.events.includes(env.invalidEvent),false)
  })
  test(`${role}: newer login is not removed by an older failed refresh`,async()=>{
    let env
    env=setup(role,async req=>{
      if(req.url.endsWith('/refresh')) {env.put('new-login','new-login-refresh');return json(401)}
      return json(req.headers.get('Authorization')==='Bearer new-login'?200:401)
    })
    assert.equal((await env.fetch('/api/v1/data')).status,200)
    assert.equal(env.get().refreshToken,'new-login-refresh')
  })
  test(`${role}: authorization is never injected into another origin`,async()=>{
    let auth
    const env=setup(role,async req=>{auth=req.headers.get('Authorization');return json(200)})
    await env.fetch('https://external.example.invalid/resource')
    assert.equal(auth,null)
  })
}
