import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import test from 'node:test';
import { DefaultResourceLoader } from '@earendil-works/pi-coding-agent';
import { generateDeepResearchWorkflow } from '@quintinshaw/pi-dynamic-workflows';
import { resolveResearchModel } from './research-routing.mjs';

const root = resolve(import.meta.dirname, '../..');
const readConfig = async (name) => JSON.parse(await readFile(resolve(root, 'configs/pi', name), 'utf8'));

test('four models use the metered local gateway and a separate credential', async () => {
  const { providers } = await readConfig('models.json');
  assert.deepEqual(Object.keys(providers), ['cua-litellm']);
  const provider = providers['cua-litellm'];
  assert.equal(provider.baseUrl, 'http://127.0.0.1:8765/v1');
  assert.equal(provider.apiKey, '$GAMEWORLD_RESEARCH_TOKEN');
  assert.equal(provider.api, 'openai-completions');
  assert.deepEqual(provider.models.map((model) => model.id), ['astra', 'gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna']);
  const { tiers } = await readConfig('model-tiers.json');
  for (const model of Object.values(tiers)) {
    assert.ok(provider.models.some((entry) => model === `cua-litellm/${entry.id}`));
  }
});

test('deep-research roles match the pinned upstream script', () => {
  const script = generateDeepResearchWorkflow();
  const roles = { 'plan queries': 'gpt-5.6-luna', 'cross-check': 'gpt-5.6-sol', 'write report': 'astra' };
  for (const [label, model] of Object.entries(roles)) {
    assert.ok(script.includes(`label: '${label}'`));
    assert.deepEqual(resolveResearchModel({ modelSource: 'default', label }), { action: 'use', model: `cua-litellm/${model}` });
  }
  assert.ok(script.includes("label: 'research ' +"));
  assert.equal(resolveResearchModel({ modelSource: 'session', label: 'research 1' }).model, 'cua-litellm/gpt-5.6-terra');
});

test('explicit model, tier and phase selections remain authoritative', () => {
  for (const modelSource of ['explicit', 'tier', 'phase']) {
    assert.deepEqual(resolveResearchModel({ modelSource, label: 'write report' }), { action: 'unchanged' });
  }
  assert.deepEqual(resolveResearchModel({ modelSource: 'default', label: 'other task' }), { action: 'unchanged' });
});

test('workflow defaults bound concurrency, retries and time', async () => {
  const settings = await readConfig('workflow-settings.json');
  assert.equal(settings.defaultConcurrency, 2);
  assert.equal(settings.defaultAgentRetries, 0);
  assert.equal(settings.defaultAgentTimeoutMs, 600000);
  assert.equal(settings.keywordTriggerEnabled, false);
  assert.ok(settings.defaultTokenBudget > 0);
});

test('installed pi loads the workflow, routing extension and research instructions', async () => {
  const loader = new DefaultResourceLoader({ cwd: root, agentDir: resolve(root, '.pi-local/agent') });
  await loader.reload();
  const result = loader.getExtensions();
  assert.deepEqual(result.errors, []);
  assert.ok(result.extensions.some((extension) => extension.commands.has('deep-research')));
  assert.ok(result.extensions.some((extension) => extension.path.endsWith('research-routing.mjs')));
  assert.ok(loader.getAgentsFiles().agentsFiles.some((file) => file.content.includes('GameWorld research supervisor')));
});

test('campaign tokens and Modal dollars use separate controller gates', async () => {
  const limits = await readConfig('research-limits.json');
  assert.equal(limits.litellm.total_token_limit, 1000000000);
  assert.equal(limits.litellm.scope, 'campaign');
  assert.equal(limits.litellm.dollar_budget, null);
  assert.equal(limits.modal.spending_cap_usd, 2000);
  assert.equal(limits.modal.normal_work_allowance_usd + limits.modal.shutdown_reserve_usd, 2000);
  assert.equal(limits.litellm.enforcement_status, 'controller_gateway_reservations_pending_provider_reconciliation');
  assert.equal(limits.modal.enforcement_status, 'campaign_controller_reservations_pending_live_reconciliation');
});
