import test from 'node:test';
import assert from 'node:assert/strict';
import {createExperienceManifest,validateExperienceManifest,normalizeBindingsManifest,extractBindingKeys,applyBindingsToHtml,createThemeTokens,themeTokensToCss,mapThemeToHostTokens,createTemplateRuntimeSdk,createExperienceEditorPolicy,experienceCan} from '../src/index.js';

test('Experience Contract v2 cria Landing e Booking sem Login template',()=>{
  const m=createExperienceManifest({package:{key:'studio-demo',name:'Studio Demo'}});
  assert.equal(m.schema,'argws-experience-package/v2');
  assert.equal(m.pages.landing.surface,'LANDING');
  assert.equal(m.pages.booking.surface,'BOOKING');
  assert.equal('login' in m.pages,false);
  assert.equal(validateExperienceManifest(m).valid,true);
});

test('Bindings v1 preservam HTML e alteram somente campos declarados',()=>{
  const html='<section><h1 data-sp-bind="hero.title">Original</h1><a data-sp-show="show_booking" href="/agendar">Agendar</a></section>';
  assert.deepEqual(extractBindingKeys(html).sort(),['hero.title','show_booking']);
  const output=applyBindingsToHtml(html,{'hero.title':'Novo título',show_booking:false},{'hero.title':{type:'text'}});
  assert.match(output,/Novo título/);assert.doesNotMatch(output,/Agendar/);assert.match(output,/<section>/);
});

test('Theme Tokens geram CSS e tokens de host sem injetar CSS arbitrário',()=>{
  const theme=createThemeTokens({colors:{primary:'#c31f62'},typography:{heading:'Playfair Display'}});
  assert.equal(theme.colors.primary,'#c31f62');
  assert.match(themeTokensToCss(theme),/--avb-primary:#c31f62/);
  assert.equal(mapThemeToHostTokens(theme)['--sp-primary'],'#c31f62');
});

test('Theme Tokens aceitam Proxy reativo sem structuredClone/DataCloneError',()=>{
  const branding=new Proxy({logo:'assets/logo.svg',nested:{name:'Marca do template'}},{});
  const theme=createThemeTokens({branding});
  assert.deepEqual(theme.branding,{logo:'assets/logo.svg',nested:{name:'Marca do template'}});
  assert.doesNotThrow(()=>themeTokensToCss(new Proxy(theme,{})));
});

test('Template Runtime SDK delega motor de booking ao host',async()=>{
  const calls=[];
  const sdk=createTemplateRuntimeSdk({
    async getContext(){return{tenant:'demo'}},
    async bookingCatalog(input){calls.push(['catalog',input]);return[{id:'1'}]},
    async bookingAvailability(input){calls.push(['availability',input]);return['10:00']},
    async bookingCreate(input){calls.push(['create',input]);return{id:'appt'}},
    async track(input){calls.push(['track',input]);return{accepted:true}},
  });
  assert.equal((await sdk.context.get()).tenant,'demo');
  assert.equal((await sdk.booking.catalog()).length,1);
  assert.equal((await sdk.booking.availability({date:'2026-08-28'}))[0],'10:00');
  assert.equal((await sdk.booking.create({name:'Ana'})).id,'appt');
  await sdk.analytics.track('booking_completed',{value:1});
  assert.deepEqual(calls.map(x=>x[0]),['catalog','availability','create','track']);
});

test('Permissões permitem editor básico sem código',()=>{
  const basic=createExperienceEditorPolicy('basic');
  assert.equal(experienceCan(basic,'edit.text'),true);
  assert.equal(experienceCan(basic,'code.edit'),false);
  const dev=createExperienceEditorPolicy('developer');
  assert.equal(experienceCan(dev,'code.edit'),true);
});
