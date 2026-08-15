export type ApiResponse<T> = { data: T; meta: Record<string, unknown> }
export type TenantContext = { tenant_id: string; slug: string; hostname: string; timezone: string }
export type AppointmentStatus = 'PENDING'|'AWAITING_CONFIRMATION'|'CONFIRMED'|'CHECKED_IN'|'IN_PROGRESS'|'COMPLETED'|'CANCELLED'|'NO_SHOW'
