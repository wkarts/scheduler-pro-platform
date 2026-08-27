const ALL_CAPABILITIES = [
  'editor.open','content.edit','element.add','element.delete','element.move','style.edit','advanced.edit','design_system.edit','seo.edit',
  'template.apply','library.manage','asset.upload','custom_code.edit','data_source.configure','history.restore','page.import','page.export','page.save','page.publish',
];
export { ALL_CAPABILITIES };

export function createEditorPolicy({ role='admin', capabilities=null, denied=[] } = {}) {
  const defaults = role === 'content_editor'
    ? ['editor.open','content.edit','page.save']
    : role === 'designer'
      ? ALL_CAPABILITIES.filter(item => !['custom_code.edit','data_source.configure','page.publish'].includes(item))
      : role === 'viewer' ? ['editor.open'] : [...ALL_CAPABILITIES];
  const allowed = new Set(Array.isArray(capabilities) ? capabilities : defaults);
  for (const item of denied || []) allowed.delete(item);
  return { role, capabilities:Array.from(allowed) };
}

export function can(policy, capability) {
  if (!policy) return true;
  const list = Array.isArray(policy.capabilities) ? policy.capabilities : [];
  return list.includes('*') || list.includes(capability);
}

export function assertCan(policy, capability, message = 'Operação não permitida para este perfil.') {
  if (!can(policy, capability)) { const error = new Error(message); error.code = 'UPB_PERMISSION_DENIED'; throw error; }
  return true;
}

export function policyForRole(role, config = {}) {
  const definition = config?.roles?.[role];
  return definition ? createEditorPolicy({ role, capabilities:definition.capabilities, denied:definition.denied }) : createEditorPolicy({ role });
}
