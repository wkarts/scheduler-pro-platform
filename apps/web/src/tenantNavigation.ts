export const AGENDA_OPERATOR_EVENT = 'scheduler-pro-agenda-operator'

export type AgendaOperatorTab = 'quick' | 'recurring' | 'swap' | 'manage'
export type AgendaOperatorDetail = {
  tab?: AgendaOperatorTab
  startsAt?: string
  customerId?: string
}


export function openAgendaOperator(detail: AgendaOperatorDetail = {}): void {
  window.dispatchEvent(new CustomEvent<AgendaOperatorDetail>(AGENDA_OPERATOR_EVENT, { detail }))
}
