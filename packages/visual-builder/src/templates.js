import { addNode, createDocument, createNode } from './model.js';
import { createProps } from './registry.js';

function node(type, props={}, extra={}) { return createNode(type,{...createProps(type),...props},extra); }
export function blankTemplate() { return createDocument({title:'Página em branco'}); }

export function schedulerTemplate() {
  const doc=createDocument({title:'Scheduler Pro — Conversão',globalStyles:{primary:'#3151cf',secondary:'#12192a',accent:'#8e93ff',background:'#ffffff',text:'#182237'}});
  [
    node('hero',{eyebrow:'Atendimento sob medida',title:'Seu horário, do seu jeito',text:'Conheça nossos serviços e escolha o melhor momento para ser atendido.',cta:'Agendar agora'}),
    node('services',{title:'Serviços',subtitle:'Escolha o atendimento ideal',show_prices:true}),
    node('professionals',{title:'Quem vai atender você'}),
    node('testimonials',{title:'O que nossos clientes dizem',items:[{name:'Cliente',text:'Atendimento excelente e agendamento muito simples.'}]}),
    node('faq',{title:'Perguntas frequentes',items:[{question:'Como funciona o agendamento?',answer:'Escolha o serviço, o profissional e um horário disponível.'}]}),
    node('booking',{title:'Escolha seu horário',subtitle:'Selecione serviço, profissional, data e horário.'}),
    node('contact',{title:'Contato'}),node('footer',{text:'Atendimento com hora marcada e organização.'}),
  ].forEach(n=>addNode(doc,n)); return doc;
}

export function genericBusinessTemplate() {
  const doc=createDocument({title:'Landing Page — Negócio',globalStyles:{primary:'#2563eb',secondary:'#0f172a',accent:'#38bdf8',background:'#ffffff',text:'#172033'}});
  addNode(doc,node('nav_menu',{brand:'Sua marca',items_text:'Início | #inicio\nBenefícios | #beneficios\nContato | #contato'}));
  const hero=addNode(doc,node('hero',{eyebrow:'Sua empresa',title:'Uma proposta de valor que fica clara em segundos',text:'Explique o benefício principal, construa confiança e conduza o visitante para uma ação.',cta:'Fale conosco',cta_url:'#contato'})); hero.meta.anchor='inicio';
  const grid=addNode(doc,node('grid',{columns:3,gap:22}));grid.meta.anchor='beneficios';
  addNode(doc,node('icon_box',{icon:'⚡',title:'Rápido',text:'Entregue valor com um fluxo direto e simples.'}),grid.id);addNode(doc,node('icon_box',{icon:'✓',title:'Confiável',text:'Comunique segurança, prova e diferenciais.'}),grid.id);addNode(doc,node('icon_box',{icon:'↗',title:'Escalável',text:'Prepare a página para crescer com seu projeto.'}),grid.id);
  const form=addNode(doc,node('form',{title:'Vamos conversar?',fields_text:'Nome | name | text | required\nE-mail | email | email | required\nMensagem | message | textarea | required'}));form.meta.anchor='contato';
  addNode(doc,node('footer',{text:'Todos os direitos reservados.'})); return doc;
}

export function portfolioTemplate() {
  const doc=createDocument({title:'Portfólio profissional',globalStyles:{primary:'#a855f7',secondary:'#18181b',accent:'#f0abfc',background:'#fafafa',text:'#27272a'}});
  addNode(doc,node('hero',{eyebrow:'Portfólio',title:'Trabalho que fala por si',text:'Apresente sua especialidade, seus melhores trabalhos e um caminho direto para contato.',cta:'Ver trabalhos',cta_url:'#trabalhos'}));
  const gallery=addNode(doc,node('gallery',{title:'Projetos recentes',layout:'editorial',images:[]}));gallery.meta.anchor='trabalhos';addNode(doc,node('testimonials',{title:'Recomendações',items:[]}));addNode(doc,node('contact',{title:'Vamos conversar?'}));addNode(doc,node('footer',{text:'Portfólio profissional.'}));return doc;
}

export function proConversionTemplate() {
  const doc=createDocument({title:'Conversão Pro',globalStyles:{primary:'#7c3aed',secondary:'#111827',accent:'#22d3ee',background:'#ffffff',text:'#172033'}});
  doc.design_system.classes={
    elevated:{style:{boxShadow:'0 20px 60px rgba(15,23,42,.12)',borderRadius:24,backgroundColor:'#ffffff'},states:{hover:{transform:'translateY(-4px)',boxShadow:'0 28px 80px rgba(15,23,42,.18)'}}},
    compact:{style:{padding:24}},
  };
  addNode(doc,node('nav_menu',{brand:'ARGWS',items_text:'Solução | #solucao\nPlanos | #planos\nContato | #contato'}));
  const hero=addNode(doc,node('hero',{eyebrow:'Builder profissional',title:'Crie, publique e reutilize sem depender de um CMS',text:'Um editor visual para landing pages, sites, formulários, dados dinâmicos e integrações.',cta:'Quero conhecer',cta_url:'#contato'}));hero.motion={entrance:'fade',duration:700};
  const features=addNode(doc,node('grid',{columns:3,gap:20}));features.meta.anchor='solucao';for(const [icon,title,text] of [['▦','Layout visual','Containers Flex e Grid aninhados.'],['ƒx','Dados dinâmicos','Bindings, loops e condições.'],['◎','Conversão','Forms, popups e CTAs.']]){const n=addNode(doc,node('icon_box',{icon,title,text}),features.id);n.meta.classes=['elevated','compact'];}
  const pricing=addNode(doc,node('grid',{columns:3,gap:18}));pricing.meta.anchor='planos';for(const [name,price] of [['Starter','R$ 97'],['Pro','R$ 197'],['Business','R$ 397']])addNode(doc,node('price_table',{name,price,features_text:'Editor visual\nResponsivo\nTemplates\nPublicação',button:'Escolher'}),pricing.id);
  const form=addNode(doc,node('form',{title:'Receba uma proposta',submit_label:'Enviar contato'}));form.meta.anchor='contato';
  const popup=addNode(doc,node('popup',{name:'oferta',trigger:'exit',width:520}));addNode(doc,node('heading',{text:'Antes de sair…',level:'h2'}),popup.id);addNode(doc,node('text',{text:'Deixe seu contato e receba uma demonstração.'}),popup.id);addNode(doc,node('form',{title:'',fields_text:'E-mail | email | email | required',submit_label:'Receber demonstração'}),popup.id);
  addNode(doc,node('footer',{text:'ARGWS Visual Builder Pro.'}));return doc;
}

export const BUILTIN_TEMPLATES=[
  {key:'blank',name:'Em branco',description:'Comece do zero.',create:blankTemplate},
  {key:'scheduler',name:'Scheduler Pro',description:'Serviços, profissionais, prova social e agenda.',create:schedulerTemplate},
  {key:'business',name:'Negócio / Serviço',description:'Landing genérica com menu, benefícios e formulário.',create:genericBusinessTemplate},
  {key:'portfolio',name:'Portfólio',description:'Hero, galeria, prova social e contato.',create:portfolioTemplate},
  {key:'pro-conversion',name:'Conversão Pro',description:'Design system, pricing, formulário e popup de saída.',create:proConversionTemplate},
];
