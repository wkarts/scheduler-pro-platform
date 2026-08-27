import { addNode, createDocument, createNode } from './model.js';
import { createProps } from './registry.js';

function node(type, props={}, extra={}) { return createNode(type,{...createProps(type),...props},extra); }
export function blankTemplate() { return createDocument({title:'Página em branco'}); }
export function schedulerTemplate() {
  const doc=createDocument({title:'Scheduler Pro — Conversão',globalStyles:{primary:'#3151cf',secondary:'#12192a',accent:'#8e93ff',background:'#ffffff',text:'#182237'}});
  [node('hero',{eyebrow:'Atendimento sob medida',title:'Seu horário, do seu jeito',text:'Conheça nossos serviços e escolha o melhor momento para ser atendido.',cta:'Agendar agora'}),node('services',{title:'Serviços',subtitle:'Escolha o atendimento ideal',show_prices:true}),node('professionals',{title:'Quem vai atender você'}),node('testimonials',{title:'O que nossos clientes dizem',items:[{name:'Cliente',text:'Atendimento excelente e agendamento muito simples.'}]}),node('faq',{title:'Perguntas frequentes',items:[{question:'Como funciona o agendamento?',answer:'Escolha o serviço, o profissional e um horário disponível.'}]}),node('booking',{title:'Escolha seu horário',subtitle:'Selecione serviço, profissional, data e horário.'}),node('contact',{title:'Contato'}),node('footer',{text:'Atendimento com hora marcada e organização.'})].forEach(n=>addNode(doc,n));
  return doc;
}
export function genericBusinessTemplate() {
  const doc=createDocument({title:'Landing Page — Negócio',globalStyles:{primary:'#2563eb',secondary:'#0f172a',accent:'#38bdf8',background:'#ffffff',text:'#172033'}});
  addNode(doc,node('hero',{eyebrow:'Sua empresa',title:'Uma proposta de valor que fica clara em segundos',text:'Explique o benefício principal, construa confiança e conduza o visitante para uma ação.',cta:'Fale conosco'}));
  const grid=addNode(doc,node('grid',{columns:3,gap:22}));
  addNode(doc,node('card',{title:'Benefício 1',text:'Mostre um ganho concreto para o cliente.'}),grid.id); addNode(doc,node('card',{title:'Benefício 2',text:'Explique por que sua solução é diferente.'}),grid.id); addNode(doc,node('card',{title:'Benefício 3',text:'Remova uma objeção importante.'}),grid.id); addNode(doc,node('cta',{title:'Pronto para conversar?',text:'Use esta chamada para conduzir o próximo passo.',button:'Entrar em contato'})); addNode(doc,node('footer',{text:'Todos os direitos reservados.'}));
  return doc;
}
export function portfolioTemplate() {
  const doc=createDocument({title:'Portfólio profissional',globalStyles:{primary:'#a855f7',secondary:'#18181b',accent:'#f0abfc',background:'#fafafa',text:'#27272a'}});
  addNode(doc,node('hero',{eyebrow:'Portfólio',title:'Trabalho que fala por si',text:'Apresente sua especialidade, seus melhores trabalhos e um caminho direto para contato.',cta:'Ver trabalhos'})); addNode(doc,node('gallery',{title:'Projetos recentes',layout:'editorial',images:[]})); addNode(doc,node('testimonials',{title:'Recomendações',items:[]})); addNode(doc,node('contact',{title:'Vamos conversar?'})); addNode(doc,node('footer',{text:'Portfólio profissional.'})); return doc;
}
export const BUILTIN_TEMPLATES=[{key:'blank',name:'Em branco',description:'Comece do zero.',create:blankTemplate},{key:'scheduler',name:'Scheduler Pro',description:'Serviços, profissionais, prova social e agenda.',create:schedulerTemplate},{key:'business',name:'Negócio / Serviço',description:'Landing genérica de conversão.',create:genericBusinessTemplate},{key:'portfolio',name:'Portfólio',description:'Hero, galeria, prova social e contato.',create:portfolioTemplate}];
