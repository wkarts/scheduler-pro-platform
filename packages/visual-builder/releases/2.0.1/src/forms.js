export function normalizeFormField(field = {}, index = 0) {
  const allowed = new Set(['text','email','tel','number','date','time','datetime-local','url','password','checkbox','radio','textarea','select','file','hidden','range','color']);
  const type = allowed.has(String(field.type)) ? String(field.type) : 'text';
  const name = String(field.name || `field_${index+1}`).trim().replace(/[^a-zA-Z0-9_.-]/g,'_');
  return {
    label:String(field.label || name), name, type, required:Boolean(field.required), placeholder:String(field.placeholder || ''), value:field.value ?? '',
    options:Array.isArray(field.options) ? field.options : [], accept:String(field.accept || ''), step:Math.max(1,Number(field.step || 1)), min:field.min ?? null, max:field.max ?? null,
  };
}

export function normalizeFormSchema(value = {}) {
  const rawFields = Array.isArray(value.fields) ? value.fields : [];
  const fields = rawFields.map(normalizeFormField);
  const steps = Math.max(1, ...fields.map(field => field.step || 1));
  return { id:String(value.id || 'form'), fields, steps, actions:Array.isArray(value.actions) ? value.actions : [], success_message:String(value.success_message || 'Enviado com sucesso.'), error_message:String(value.error_message || 'Não foi possível enviar.') };
}

export function validateFormValues(schema, values = {}) {
  const normalized = normalizeFormSchema(schema); const errors = {};
  for (const field of normalized.fields) {
    const value = values[field.name];
    if (field.required && (value == null || value === '' || value === false)) errors[field.name] = 'Campo obrigatório.';
    if (field.type === 'email' && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value))) errors[field.name] = 'E-mail inválido.';
    if (field.type === 'url' && value) { try { new URL(String(value)); } catch { errors[field.name] = 'URL inválida.'; } }
    if (field.type === 'number' && value !== '' && !Number.isFinite(Number(value))) errors[field.name] = 'Número inválido.';
  }
  return { valid:!Object.keys(errors).length, errors };
}

export function parseFormFieldsText(value) {
  return String(value || '').split(/\r?\n/).map(line=>line.trim()).filter(Boolean).map((line,index)=>{
    const [label='',name='',type='text',required='',options='',step='1'] = line.split('|').map(v=>v.trim());
    return normalizeFormField({ label, name:name || label.toLowerCase().replace(/[^a-z0-9]+/gi,'_'), type, required:/^(required|sim|true|1)$/i.test(required), options:options ? options.split(',').map(v=>v.trim()).filter(Boolean) : [], step:Number(step || 1) }, index);
  });
}
