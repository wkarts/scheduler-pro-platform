const text = (key, label, defaultValue = '') => ({ key, label, control: 'text', default: defaultValue });
const textarea = (key, label, defaultValue = '') => ({ key, label, control: 'textarea', default: defaultValue });
const toggle = (key, label, defaultValue = false) => ({ key, label, control: 'toggle', default: defaultValue });
const select = (key, label, options, defaultValue) => ({ key, label, control: 'select', options, default: defaultValue });
const number = (key, label, defaultValue = 0, min = 0, max = 9999) => ({ key, label, control: 'number', default: defaultValue, min, max });

export const WIDGETS = {
  container: { label: 'Container', group: 'Layout', icon: '▣', acceptsChildren: true, defaults: { direction: 'column', gap: 20, align: 'stretch', justify: 'flex-start', max_width: 1180 }, fields: [select('direction','Direção',[['row','Horizontal'],['column','Vertical']],'column'), number('gap','Espaço',20,0,160), number('max_width','Largura máxima',1180,240,2400)] },
  grid: { label: 'Grid', group: 'Layout', icon: '▦', acceptsChildren: true, defaults: { columns: 3, gap: 20 }, fields: [number('columns','Colunas',3,1,12), number('gap','Espaço',20,0,160)] },
  hero: { label: 'Hero', group: 'Marketing', icon: '★', defaults: { eyebrow:'Seu negócio',title:'Transforme visitantes em clientes',text:'Construa uma apresentação clara e conduza o visitante para a ação.',cta:'Começar agora',image:'' }, fields:[text('eyebrow','Sobretítulo'),text('title','Título'),textarea('text','Texto'),text('cta','Texto do botão'),text('image','Imagem (URL)')] },
  heading: { label: 'Título', group: 'Básico', icon: 'H', defaults:{text:'Novo título',level:'h2'}, fields:[text('text','Texto'),select('level','Nível',[['h1','H1'],['h2','H2'],['h3','H3'],['h4','H4']],'h2')] },
  title: { label: 'Título compatível', group: 'Scheduler Pro', icon: 'T', defaults:{text:'Novo título'}, fields:[text('text','Texto')] },
  subtitle: { label: 'Subtítulo', group: 'Scheduler Pro', icon: 't', defaults:{text:'Novo subtítulo'}, fields:[text('text','Texto')] },
  text: { label:'Texto', group:'Básico', icon:'¶', defaults:{title:'',text:'Digite seu texto aqui.'}, fields:[text('title','Título'),textarea('text','Texto')] },
  button: { label:'Botão', group:'Básico', icon:'▰', defaults:{label:'Saiba mais',url:'#'}, fields:[text('label','Rótulo'),text('url','Link')] },
  image: { label:'Imagem', group:'Básico', icon:'▧', defaults:{image:'',alt:'Imagem'}, fields:[text('image','URL da imagem'),text('alt','Texto alternativo')] },
  video: { label:'Vídeo', group:'Básico', icon:'▶', defaults:{title:'Vídeo',url:''}, fields:[text('title','Título'),text('url','URL')] },
  divider: { label:'Divisor', group:'Básico', icon:'—', defaults:{}, fields:[] },
  spacer: { label:'Espaçador', group:'Básico', icon:'↕', defaults:{height:32}, fields:[number('height','Altura',32,0,800)] },
  gallery: { label:'Galeria', group:'Marketing', icon:'▦', defaults:{title:'Galeria',layout:'grid',images:[]}, fields:[text('title','Título'),select('layout','Layout',[['grid','Grade'],['editorial','Editorial']],'grid'),textarea('images_text','URLs (uma por linha)')] },
  card: { label:'Card', group:'Marketing', icon:'▤', defaults:{title:'Título do card',text:'Conteúdo do card'}, fields:[text('title','Título'),textarea('text','Texto')] },
  services: { label:'Serviços', group:'Scheduler Pro', icon:'✦', defaults:{title:'Serviços',subtitle:'Escolha o atendimento ideal',show_prices:true}, fields:[text('title','Título'),text('subtitle','Subtítulo'),toggle('show_prices','Mostrar preços',true)] },
  professionals: { label:'Profissionais', group:'Scheduler Pro', icon:'♙', defaults:{title:'Profissionais',layout:'cards'}, fields:[text('title','Título')] },
  booking: { label:'Agenda / Agendamento', group:'Scheduler Pro', icon:'▣', defaults:{title:'Escolha seu horário',subtitle:'Selecione serviço, profissional, data e horário.'}, fields:[text('title','Título'),text('subtitle','Subtítulo')] },
  testimonials: { label:'Depoimentos', group:'Marketing', icon:'❝', defaults:{title:'Depoimentos',items:[]}, fields:[text('title','Título'),textarea('items_text','Itens: Nome | Texto, um por linha')] },
  faq: { label:'FAQ', group:'Marketing', icon:'?', defaults:{title:'Perguntas frequentes',items:[]}, fields:[text('title','Título'),textarea('items_text','Itens: Pergunta | Resposta, um por linha')] },
  business_hours: { label:'Horários', group:'Scheduler Pro', icon:'◷', defaults:{title:'Horários de atendimento'}, fields:[text('title','Título')] },
  address: { label:'Endereço', group:'Scheduler Pro', icon:'⌖', defaults:{title:'Onde estamos',address:'',show_map:true}, fields:[text('title','Título'),textarea('address','Endereço'),toggle('show_map','Mostrar mapa',true)] },
  contact: { label:'Contato', group:'Scheduler Pro', icon:'☎', defaults:{title:'Contato',phone:'',email:''}, fields:[text('title','Título'),text('phone','Telefone'),text('email','E-mail')] },
  social: { label:'Redes sociais', group:'Marketing', icon:'◎', defaults:{title:'Redes sociais',instagram:'',facebook:'',tiktok:''}, fields:[text('title','Título'),text('instagram','Instagram'),text('facebook','Facebook'),text('tiktok','TikTok')] },
  whatsapp_button: { label:'WhatsApp', group:'Scheduler Pro', icon:'◉', defaults:{label:'Falar pelo WhatsApp',phone:''}, fields:[text('label','Rótulo'),text('phone','Telefone')] },
  cta: { label:'Chamada para ação', group:'Marketing', icon:'→', defaults:{title:'Pronto para começar?',text:'Escolha a melhor opção para você.',button:'Continuar'}, fields:[text('title','Título'),textarea('text','Texto'),text('button','Botão')] },
  footer: { label:'Rodapé', group:'Layout', icon:'▁', defaults:{text:'Todos os direitos reservados.'}, fields:[text('text','Texto')] },
  html: { label:'HTML seguro', group:'Avançado', icon:'</>', defaults:{html:'<p>HTML personalizado</p>'}, fields:[textarea('html','HTML')] },
};

export function widgetDefinition(type) { return WIDGETS[type] || { label:type, group:'Outros', icon:'◇', defaults:{title:'Novo bloco'}, fields:[text('title','Título')] }; }
export function widgetGroups() { const groups = {}; for (const [type, def] of Object.entries(WIDGETS)) (groups[def.group] ||= []).push({ type, ...def }); return groups; }
export function createProps(type) { return JSON.parse(JSON.stringify(widgetDefinition(type).defaults || {})); }
export function registerWidget(type, definition) { if (!/^[a-z][a-z0-9_-]{1,63}$/.test(String(type))) throw new Error('Tipo de widget inválido.'); if (!definition || typeof definition !== 'object' || !definition.label) throw new Error('Definição de widget inválida.'); WIDGETS[type] = { group:'Extensões', icon:'◇', defaults:{}, fields:[], ...definition }; return WIDGETS[type]; }
export function unregisterWidget(type) { delete WIDGETS[type]; }
