import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { mkdtemp, mkdir, rm, readFile, realpath, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, sep } from 'node:path';
import { isIP } from 'node:net';

export const BROWSER_TOOLS = new Set([
  'browser_navigate', 'browser_navigate_back', 'browser_snapshot', 'browser_click',
  'browser_type', 'browser_press_key', 'browser_tabs', 'browser_close',
]);

export function validateBrowserArguments(params) {
  if ('filename' in params) throw new Error('Saving arbitrary browser files is disabled.');
  if (!params.url) return;
  const url = new URL(params.url);
  const host = url.hostname.toLowerCase();
  if (url.protocol !== 'https:' || url.username || url.password || url.port
      || !host.includes('.') || isIP(host) || host.startsWith('[')
      || /(?:^|\.)(localhost|local|internal|svc|cluster\.local)$/.test(host)) {
    throw new Error('Research navigation requires a public HTTPS hostname without credentials or a custom port.');
  }
}

export function browserEnvironment(directory) {
  return {
    PATH: process.env.PATH ?? '/usr/bin:/bin',
    HOME: directory,
    TMPDIR: directory,
    XDG_CACHE_HOME: resolve(directory, 'cache'),
    XDG_CONFIG_HOME: resolve(directory, 'config'),
    LANG: 'C.UTF-8',
  };
}


export async function expandSnapshots(text, directory) {
  const outputRoot = await realpath(resolve(directory, 'output'));
  let expanded = text;
  for (const match of text.matchAll(/\[Snapshot\]\((output\/page-[a-zA-Z0-9.-]+\.yml)\)/g)) {
    const path = await realpath(resolve(directory, match[1]));
    if (!path.startsWith(outputRoot + sep)) throw new Error('Snapshot escaped browser output directory.');
    if ((await stat(path)).size > 4 * 1024 * 1024) throw new Error('Browser snapshot exceeds 4 MiB.');
    expanded += '\n' + await readFile(path, 'utf8');
  }
  return expanded;
}

export function isBlockedPage(text) {
  return /google\.[^/]+\/sorry\//i.test(text)
    || /- HTTP status: (?:403|429)\b/.test(text)
    || /Please complete the following challenge to confirm this search was made by a human/i.test(text);
}

export async function createBrowserSession(config, record = () => {}) {
  const directory = await mkdtemp(resolve(tmpdir(), 'gameworld-research-browser-'));
  await mkdir(resolve(directory, 'output'));
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [resolve(import.meta.dirname, 'node_modules/@playwright/mcp/cli.js'),
      '--headless', '--isolated', '--browser', 'chrome',
      '--executable-path', process.env.PLAYWRIGHT_EXECUTABLE_PATH ?? '/usr/bin/chromium',
      '--block-service-workers', '--image-responses', 'omit', '--codegen', 'none',
      '--timeout-navigation', String(config.navigation_timeout_ms),
      '--output-dir', resolve(directory, 'output'), '--output-max-size', '4194304'],
    cwd: directory,
    env: browserEnvironment(directory),
    stderr: 'pipe',
  });
  const client = new Client({ name: 'gameworld-browser-research', version: '1.0.0' });
  let closed = false;
  let calls = 0;
  let browserStarted = false;
  const visited = new Set();
  const blockedHosts = new Set();
  let pageBlocked = false;
  const close = async () => {
    if (closed) return;
    closed = true;
    try { await client.close(); } finally {
      await transport.close();
      await rm(directory, { recursive: true, force: true });
    }
  };
  try {
    await client.connect(transport, { timeout: 20000 });
    transport.stderr?.on('data', () => {});
    const inventory = await client.listTools();
    const tools = inventory.tools.filter((tool) => BROWSER_TOOLS.has(tool.name)).map((tool) => {
      const parameters = structuredClone(tool.inputSchema);
      if (parameters.properties) delete parameters.properties.filename;
      if (parameters.required) parameters.required = parameters.required.filter((name) => name !== 'filename');
      return {
        name: tool.name,
        label: tool.name,
        description: tool.description,
        parameters,
        async execute(_id, params, signal) {
          signal?.throwIfAborted();
          if (closed) throw new Error('Browser session is closed.');
          validateBrowserArguments(params);
          if (params.url && blockedHosts.has(new URL(params.url).hostname)) throw new Error('Search host is blocked for this worker; use another source without bypassing the challenge.');
          if (pageBlocked && !['browser_navigate', 'browser_snapshot', 'browser_close'].includes(tool.name)) throw new Error('Interaction with a blocked/challenge page is disabled.');
          if (++calls > config.browser_tool_limit) throw new Error('Research browser tool-call limit reached.');
          const started = performance.now();
          const result = await client.callTool({ name: tool.name, arguments: params }, undefined,
            { signal, timeout: config.navigation_timeout_ms + 10000 });
          browserStarted = true;
          const rawText = (result.content ?? []).filter((part) => part.type === 'text').map((part) => part.text).join('\n');
          const text = await expandSnapshots(rawText, directory);
          pageBlocked = isBlockedPage(text);
          if (pageBlocked && params.url) blockedHosts.add(new URL(params.url).hostname);
          const toolError = Boolean(result.isError) || pageBlocked;
          for (const match of text.matchAll(/Page URL:\s*(https?:\/\/[^\s]+)/g)) visited.add(match[1]);
          record({ type: 'browser_tool', name: tool.name, url: params.url ?? null,
            seconds: (performance.now() - started) / 1000, isError: toolError,
            text, calls });
          const truncated = text.length > config.snapshot_character_limit;
          return {
            content: [{ type: 'text', text: (pageBlocked ? '[Blocked by upstream. Do not solve or bypass challenges.]\n' : '') + text.slice(0, config.snapshot_character_limit)
              + (truncated ? '\n[Browser output truncated; narrow the page or follow a specific source.]' : '') }],
            details: { isError: toolError, blocked: pageBlocked, calls, truncated },
            isError: toolError,
          };
        },
      };
    });
    if (!tools.some((tool) => tool.name === 'browser_navigate') || !tools.some((tool) => tool.name === 'browser_snapshot')) {
      throw new Error('Playwright MCP is missing the required research tools.');
    }
    record({ type: 'browser_session', directory, toolNames: tools.map((tool) => tool.name) });
    return { tools, directory, close, visited, get calls() { return calls; }, get browserStarted() { return browserStarted; } };
  } catch (error) {
    await close();
    throw error;
  }
}

let queue = Promise.resolve();
let nextSearch = 0;

export function createSearxngTool(config, record = () => {}) {
  let calls = 0;
  return {
    name: 'web_search',
    label: 'SearXNG Search',
    description: 'Find source URLs through the private SearXNG service. Fetch sources with browser_navigate before making claims. Empty results and engine errors are not proof of absent literature.',
    parameters: { type: 'object', properties: { query: { type: 'string', minLength: 1, maxLength: 1000 }, academic: { type: 'boolean' } }, required: ['query'], additionalProperties: false },
    async execute(_id, params, signal) {
      if (++calls > (config.search_tool_limit ?? 3)) throw new Error('Research search-call limit reached.');
      if (typeof params.query !== 'string' || !params.query.trim() || params.query.length > 1000) throw new Error('A nonempty query of at most 1000 characters is required.');
      const run = async () => {
        signal?.throwIfAborted();
        const wait = Math.max(0, nextSearch - Date.now());
        if (wait) await new Promise((resolveWait) => setTimeout(resolveWait, wait));
        signal?.throwIfAborted();
        nextSearch = Date.now() + config.search_interval_ms;
        const url = new URL('/search', config.searxng_url);
        url.search = new URLSearchParams({ q: params.query, format: 'json', language: 'en', engines: params.academic ? 'semantic scholar' : 'google' });
        const started = performance.now();
        try {
          const response = await fetch(url, { signal: AbortSignal.any([signal ?? new AbortController().signal, AbortSignal.timeout(25000)]) });
          if (!response.ok) throw new Error(`SearXNG HTTP ${response.status}`);
          const data = await response.json();
          if (!Array.isArray(data.results)) throw new Error('SearXNG response has no results array.');
          const results = data.results.slice(0, 10).map(({ title, url: sourceUrl, content, engines }) => ({ title, url: sourceUrl, snippet: String(content ?? '').slice(0, 600), engines }));
          const errors = data.unresponsive_engines ?? [];
          const status = results.length ? (errors.length ? 'partial' : 'results') : (errors.length ? 'failed' : 'empty');
          const result = { status, results, engine_errors: errors };
          record({ type: 'search', query: params.query, seconds: (performance.now() - started) / 1000, ...result });
          return { content: [{ type: 'text', text: JSON.stringify(result) }], details: result, isError: status === 'failed' };
        } catch (error) {
          if (signal?.aborted) throw error;
          const result = { status: 'failed', results: [], error: error.message };
          record({ type: 'search', query: params.query, ...result });
          return { content: [{ type: 'text', text: JSON.stringify(result) }], details: result, isError: true };
        }
      };
      const result = queue.then(run);
      queue = result.catch(() => {});
      return result;
    },
  };
}
