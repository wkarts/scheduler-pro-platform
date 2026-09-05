// Capture and remove credentials from the URL before installing frontend telemetry.
const fragment = window.location.hash
export const isIdentityEmailLink = fragment.startsWith('#verificar-email')
export let identityEmailToken = isIdentityEmailLink ? new URLSearchParams(fragment.split('?')[1] || '').get('token') || '' : ''
if (isIdentityEmailLink) window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#verificar-email`)
export function clearIdentityEmailToken(): void { identityEmailToken = '' }
