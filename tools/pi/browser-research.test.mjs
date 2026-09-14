import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, symlink, rm, readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { tmpdir } from 'node:os';
import test from 'node:test';
import { runWorkflow } from '@quintinshaw/pi-dynamic-workflows';
import { DefaultResourceLoader } from '@earendil-works/pi-coding-agent';
import { BROWSER_TOOLS, validateBrowserArguments, browserEnvironment, expandSnapshots, isBlockedPage } from './browser-tools.mjs';
import { BrowserResearchRunner, researchScript, validateSources, ROOT } from './browser-research.mjs';

const config = JSON.parse(await readFile(resolve(ROOT, 'configs/pi/browser-research.json'), 'utf8'));

test('browser tools omit execution, uploads and host administration', () => {
  for (const name of ['browser_run_code', 'browser_evaluate', 'browser_file_upload', 'browser_install', 'bash']) assert.ok(!BROWSER_TOOLS.has(name));
  assert.ok(BROWSER_TOOLS.has('browser_snapshot'));
});

test('direct navigation rejects local/file/credential URLs and arbitrary output files', () => {
  for (const url of ['file:///etc/passwd', 'http://example.org', 'https://127.0.0.1', 'https://2130706433', 'https://localhost', 'https://foo.svc.cluster.local', 'https://user:password@example.org', 'https://example.org:8443', 'https://[::1]']) {
    assert.throws(() => validateBrowserArguments({ url }));
  }
  assert.throws(() => validateBrowserArguments({ filename: '/tmp/other' }));
  assert.doesNotThrow(() => validateBrowserArguments({ url: 'https://modal.com/docs/examples/grpo_trl' }));
});

test('browser subprocess environment excludes provider and infrastructure credentials', () => {
  const env = browserEnvironment('/tmp/test-profile');
  for (const key of ['LITELLM_API_KEY', 'LITELLM_MASTER_KEY', 'CUA_CLIENT_SECRET', 'MODAL_TOKEN_SECRET']) assert.equal(env[key], undefined);
  assert.equal(env.HOME, '/tmp/test-profile');
});

test('snapshot artifacts expand only within their session output directory', async () => {
  const directory = await mkdtemp(resolve(tmpdir(), 'browser-artifact-test-'));
  try {
    await mkdir(resolve(directory, 'output'));
    await writeFile(resolve(directory, 'output/page-test.yml'), '- heading "Evidence"');
    assert.match(await expandSnapshots('[Snapshot](output/page-test.yml)', directory), /Evidence/);
    await writeFile(resolve(directory, 'outside.yml'), 'private');
    await symlink(resolve(directory, 'outside.yml'), resolve(directory, 'output/page-escape.yml'));
    await assert.rejects(expandSnapshots('[Snapshot](output/page-escape.yml)', directory), /escaped/);
    assert.equal(await expandSnapshots('[Snapshot](../../outside.yml)', directory), '[Snapshot](../../outside.yml)');
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test('upstream blocks are detected without treating ordinary docs as CAPTCHA', () => {
  assert.ok(isBlockedPage('- Page URL: https://www.google.com/sorry/index?q=x'));
  assert.ok(isBlockedPage('- HTTP status: 429'));
  assert.ok(isBlockedPage('Please complete the following challenge to confirm this search was made by a human'));
  assert.ok(!isBlockedPage('This paper discusses CAPTCHA detection.'));
});

test('sources require visited URL and an observed short excerpt', () => {
  const source = { url: 'https://modal.com/docs/examples/grpo_trl', evidence: 'coding problems', claims: ['Uses coding tasks'] };
  const observations = [{ url: source.url, text: 'Train a model to solve coding problems using GRPO' }];
  assert.equal(validateSources({ sources: [source], limitations: [] }, observations).sources.length, 1);
  assert.equal(validateSources({ sources: [{ ...source, url: 'https://other.org/' }] }, observations).sources.length, 0);
  assert.equal(validateSources({ sources: [{ ...source, evidence: 'invented words' }] }, observations).sources.length, 0);
});

test('gatherers get distinct browser sessions; closure occurs on success and error', async () => {
  const sessions = [];
  const agentCalls = [];
  const runner = new BrowserResearchRunner({ config, mode: 'browser', record() {},
    browserFactory: async () => {
      const session = { tools: [{ name: 'browser_snapshot' }], closed: false, async close() { this.closed = true; } };
      sessions.push(session);
      return session;
    },
    agentFactory: (options) => {
      const sessionTools = options.session.tools;
      assert.deepEqual(options.tools, []);
      assert.ok(options.session.tools.every((name) => name === 'browser_snapshot' || name === 'structured_output'));
      return { async run(prompt, options) {
        agentCalls.push(options);
        assert.deepEqual(sessionTools, [...options.tools.map((tool) => tool.name), ...(options.schema ? ['structured_output'] : [])]);
        if (prompt === 'fail') throw new Error('worker failed');
        return { sources: [], limitations: [] };
      } };
    },
  });
  await Promise.all([runner.run('ok', { label: 'research 1' }), runner.run('ok', { label: 'research 2' })]);
  await assert.rejects(runner.run('fail', { label: 'research 3' }), /worker failed/);
  assert.equal(sessions.length, 3);
  assert.ok(sessions.every((session) => session.closed));
  assert.equal(runner.sessions.size, 0);
  assert.ok(agentCalls.every((call) => call.toolNames.length === 1 && call.toolNames[0] === 'browser_snapshot'));
  await runner.run('ok', { label: 'cross-check' });
  assert.equal(sessions.length, 3);
  assert.deepEqual(agentCalls.at(-1).toolNames, []);
});

test('generated workflow executes its bounded phases with a deterministic stub', async () => {
  const labels = [];
  const result = await runWorkflow(researchScript(config), {
    cwd: ROOT, args: { question: 'test question', angles: 2 }, persistLogs: false, concurrency: 2, maxAgents: 5,
    agent: { async run(_prompt, options) {
      labels.push(options.label);
      if (options.label === 'plan queries') return { queries: ['one', 'two'] };
      if (options.label.startsWith('research ')) return { sources: [], limitations: ['test'] };
      return 'Report explicitly identifies insufficient evidence.';
    } },
  });
  assert.equal(result.agentCount, 5);
  assert.deepEqual(labels, ['plan queries', 'research 1', 'research 2', 'cross-check', 'write report']);
});

test('pi registers the new commands alongside built-in deep research', async () => {
  const loader = new DefaultResourceLoader({ cwd: ROOT, agentDir: resolve(ROOT, '.pi-local/agent') });
  await loader.reload();
  assert.deepEqual(loader.getExtensions().errors, []);
  const commands = loader.getExtensions().extensions.flatMap((extension) => [...extension.commands.keys()]);
  for (const name of ['deep-research', 'browser-research', 'hybrid-research', 'research-stop']) assert.ok(commands.includes(name));
});

test('source validation accepts a quoted excerpt spanning accessible inline nodes', () => {
  const url = 'https://example.org/paper';
  const text = '### Snapshot\n```yaml\n- paragraph:\n  - text: This uses\n  - link "GRPO":\n    - /url: https://example.org/other\n  - text: for training.\n```';
  const result = validateSources({ sources: [{ url, evidence: '"This uses GRPO for training."' }] }, [{ url, text }]);
  assert.equal(result.sources.length, 1);
  assert.equal(result.sources[0].evidence, 'This uses GRPO for training.');
});

test('aborted workers cannot allocate a browser', async () => {
  let allocations = 0;
  const runner = new BrowserResearchRunner({ config, mode: 'browser', record() {}, browserFactory: async () => { allocations++; } });
  await assert.rejects(runner.run('test', { label: 'research 1', signal: AbortSignal.abort() }));
  assert.equal(allocations, 0);
});

test('cancelling an active worker closes its browser', async () => {
  const controller = new AbortController();
  let closed = false;
  let started;
  const ready = new Promise((resolveReady) => { started = resolveReady; });
  const runner = new BrowserResearchRunner({ config, mode: 'browser', record() {},
    browserFactory: async () => ({ tools: [], async close() { closed = true; } }),
    agentFactory: () => ({ run(_prompt, options) {
      started();
      return new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(new Error('cancelled')), { once: true }));
    } }),
  });
  const running = runner.run('test', { label: 'research 1', signal: controller.signal });
  await ready;
  controller.abort();
  await assert.rejects(running, /cancelled/);
  assert.ok(closed);
  assert.equal(runner.sessions.size, 0);
});
