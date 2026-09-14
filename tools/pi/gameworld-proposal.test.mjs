import assert from 'node:assert/strict';
import test from 'node:test';

import { assembleProposal, patchSchema, proposalCoreSchema, researchQuestion } from './gameworld-proposal.mjs';


const context = {
  recommended_track: 'driver',
  baseline: {
    totals: { signals: { low_progress: 170, driver_error: 3 } },
    observations: [{ id: '01_game--01_01', signals: ['low_progress'] }],
  },
  history: [],
  driver_source_files: ['cua-driver/rust/crates/platform-linux/src/input/mod.rs'],
  sft_sources: [],
  splits: { train: ['01_game--01_01'], development: ['01_game--01_03'] },
  policy: {
    candidate_policy: { development_repeats: 2 },
    driver: { required_contract_tests: ['build', 'focus', 'held-keys', 'key-release', 'mouse-delivery'] },
    model: { minimum_grpo_group_size: 2, maximum_grpo_group_size: 8,
      maximum_trajectory_steps: 60, maximum_optimizer_steps: 32 },
    limits: { modal_micro_usd_normal: 1800000000, minimum_serving_micro_usd: 10000000 },
  },
  budget: {
    litellm_tokens: { normal_remaining: 1000000000 },
    modal_micro_usd: { normal_remaining: 1800000000 },
  },
};
const sources = [{ url: 'https://example.org/paper', evidence: 'verified', claims: ['claim'] }];
const common = {
  id: 'driver-input-fix',
  hypothesis: 'A smaller Linux input change improves delivery.',
  evidence: [{ task_id: '01_game--01_01', signal: 'low_progress' }],
  references: [{ url: sources[0].url, note: 'Primary evidence with a transfer limitation.' }],
  litellm_tokens: 1000,
  timeout_seconds: 600,
};

test('driver proposal fixes evaluator scope and zero Modal spend', () => {
  assert.match(researchQuestion(context), /cua-driver/);
  const proposal = assembleProposal({ ...common, target_paths: context.driver_source_files }, context, sources,
    '2026-09-14T00:00:00.000Z');
  assert.equal(proposal.track, 'driver');
  assert.equal(proposal.budget.desktop_episodes, 2);
  assert.equal(proposal.budget.modal_micro_usd, 0);
  assert.deepEqual(proposal.experiment.evaluation_tasks, context.splits.development);
  assert.deepEqual(proposal.experiment.contract_tests, context.policy.driver.required_contract_tests);
});

test('model proposal has explicit exact training and serving reservations', () => {
  const modelContext = { ...context, recommended_track: 'model' };
  const schema = proposalCoreSchema(modelContext, sources);
  assert.deepEqual(schema.properties.objective.enum, ['grpo']);
  const proposal = assembleProposal({ ...common, objective: 'grpo', training_tasks: context.splits.train,
    rollouts_per_task: 2, max_trajectory_steps: 4, optimizer_steps: 2,
    sft_source_id: null,
    modal_training_micro_usd: 8000000, modal_serving_micro_usd: 10000000,
  }, modelContext, sources, '2026-09-14T00:00:00.000Z');
  assert.equal(proposal.track, 'model');
  assert.equal(proposal.budget.modal_micro_usd, 18000000);
  assert.equal(proposal.budget.modal_training_micro_usd, 8000000);
  assert.equal(proposal.budget.modal_serving_micro_usd, 10000000);
});

test('unverified references and unsupported SFT are rejected', () => {
  assert.throws(() => assembleProposal({ ...common, target_paths: context.driver_source_files,
    references: [{ url: 'https://unverified.example/', note: 'not visited' }] }, context, sources,
  '2026-09-14T00:00:00.000Z'), /not browser-verified/);
  const modelContext = { ...context, recommended_track: 'model',
    sft_sources: [{ id: 'approved-source', tasks: ['other'] }] };
  assert.throws(() => assembleProposal({ ...common, objective: 'sft', training_tasks: context.splits.train,
    rollouts_per_task: 1, max_trajectory_steps: 4, optimizer_steps: 2,
    sft_source_id: 'approved-source',
    modal_training_micro_usd: 8000000, modal_serving_micro_usd: 10000000,
  }, modelContext, sources, '2026-09-14T00:00:00.000Z'), /without an authenticated source/);
});

test('driver patch schema forbids extra output fields', () => {
  assert.equal(patchSchema().additionalProperties, false);
  assert.deepEqual(patchSchema().required, ['patch', 'rationale']);
});

test('SFT scope must exactly match its immutable dataset', () => {
  const tasks = ['01_game--01_01', '01_game--01_02'];
  const modelContext = { ...context, recommended_track: 'model',
    sft_sources: [{ id: 'approved-source', tasks }] };
  const core = { ...common, objective: 'sft', training_tasks: tasks,
    rollouts_per_task: 1, max_trajectory_steps: 4, optimizer_steps: 2,
    sft_source_id: 'approved-source', modal_training_micro_usd: 8000000,
    modal_serving_micro_usd: 10000000 };
  assert.throws(() => assembleProposal({ ...core, training_tasks: tasks.slice(0, 1) },
    modelContext, sources, '2026-09-14T00:00:00.000Z'), /every task/);
  const proposal = assembleProposal(core, modelContext, sources, '2026-09-14T00:00:00.000Z');
  assert.deepEqual(proposal.experiment.training_tasks, tasks);
});
