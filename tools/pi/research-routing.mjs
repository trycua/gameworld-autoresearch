import { setPreSpawnModelResolver } from '@quintinshaw/pi-dynamic-workflows';

export function resolveResearchModel(context) {
  if (['explicit', 'tier', 'phase'].includes(context.modelSource)) {
    return { action: 'unchanged' };
  }
  const label = context.label ?? '';
  const model = label === 'plan queries' ? 'gpt-5.6-luna'
    : /^research \d+$/.test(label) ? 'gpt-5.6-terra'
    : label === 'cross-check' ? 'gpt-5.6-sol'
    : label === 'write report' ? 'astra'
    : null;
  return model ? { action: 'use', model: `cua-litellm/${model}` } : { action: 'unchanged' };
}

export default function () {
  setPreSpawnModelResolver(resolveResearchModel);
}
