export type MenuItem = { title: string; route: string; icon: string; section: 'principal'|'operacao'|'publicacao'|'sistema' }
export const menuItems: MenuItem[] = [
  { title: 'Visão geral', route: '/', icon: 'grid', section: 'principal' },
  { title: 'Agenda', route: '/agenda', icon: 'calendar', section: 'operacao' },
  { title: 'Clientes', route: '/clientes', icon: 'users', section: 'operacao' },
  { title: 'Serviços', route: '/servicos', icon: 'briefcase', section: 'operacao' },
  { title: 'Profissionais', route: '/profissionais', icon: 'badge', section: 'operacao' },
  { title: 'Landing page', route: '/landing-pages', icon: 'page', section: 'publicacao' },
  { title: 'WhatsApp API', route: '/whatsapp', icon: 'message', section: 'publicacao' },
  { title: 'Marca e aplicativo', route: '/branding', icon: 'paint', section: 'publicacao' },
  { title: 'Builds e artefatos', route: '/builds', icon: 'package', section: 'publicacao' },
  { title: 'Configurações', route: '/settings', icon: 'settings', section: 'sistema' }
]
