import { parseArgs } from 'node:util';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createBrowserSession, createSearxngTool, isBlockedPage } from './browser-tools.mjs';
import { ROOT } from './browser-research.mjs';

const { values } = parseArgs({ options: { output: { type: 'string' } } });
if (!values.output) throw new Error('--output is required');
const config = JSON.parse(await readFile(resolve(ROOT, 'configs/pi/browser-research.json'), 'utf8'));
const queries = JSON.parse(await readFile(resolve(ROOT, 'configs/searxng-research-queries.json'), 'utf8'));
await mkdir(values.output, { recursive: false });
const browser = await createBrowserSession({ ...config, browser_tool_limit: queries.length * 2 });
const search = createSearxngTool({ ...config, search_tool_limit: queries.length });
const results = [];
let blocked = false;
try {
  for (const query of queries) {
    const row = { id: query.id, query: query.query };
    const started = performance.now();
    const searx = await search.execute(query.id, { query: query.query, academic: query.kind === 'academic' });
    row.searxng = { ...searx.details, seconds: (performance.now() - started) / 1000 };
    if (blocked) {
      row.browser = { status: 'not_attempted_after_upstream_block' };
    } else {
      const browserStart = performance.now();
      const response = await browser.tools.find((tool) => tool.name === 'browser_navigate').execute(query.id,
        { url: 'https://www.google.com/search?' + new URLSearchParams({ q: query.query, num: '10' }) });
      let text = response.content[0].text;
      blocked = response.details.blocked || isBlockedPage(text);
      if (!blocked && !response.isError) {
        await new Promise((resolveWait) => setTimeout(resolveWait, 1500));
        const snapshot = await browser.tools.find((tool) => tool.name === 'browser_snapshot').execute(query.id + '-snapshot', {});
        text += '\n' + snapshot.content[0].text;
        blocked = snapshot.details.blocked || isBlockedPage(text);
      }
      const sourceUrls = [...new Set([...text.matchAll(/\/url: (https?:\/\/[^\s]+)/g)].map((match) => match[1]))]
        .filter((url) => !/(?:google\.com|gstatic\.com|googleusercontent\.com)/.test(new URL(url).hostname));
      row.browser = { status: blocked ? 'blocked' : response.isError ? 'failed' : sourceUrls.length ? 'links_observed' : 'no_source_links_observed',
        source_urls: sourceUrls, seconds: (performance.now() - browserStart) / 1000, text };
    }
    results.push(row);
    await writeFile(resolve(values.output, 'requests.json'), JSON.stringify(results, null, 2));
    console.log(`${row.id}: searxng=${row.searxng.status}, browser=${row.browser.status}`);
  }
} finally { await browser.close(); }
const attempted = results.filter((row) => row.browser.status !== 'not_attempted_after_upstream_block');
const summary = {
  at: new Date().toISOString(), model_tokens: 0, total_queries: results.length,
  searxng_nonempty: results.filter((row) => row.searxng.results.length > 0).length,
  browser_attempted: attempted.length,
  browser_blocked: attempted.filter((row) => row.browser.status === 'blocked').length,
  browser_skipped_after_block: results.length - attempted.length,
  browser_with_source_links: attempted.filter((row) => row.browser.status === 'links_observed').length,
  note: 'Operational comparison, not matched-client or relevance scoring. Browser Google and SearXNG may use different request/egress paths. Do not count skipped queries as executed failures.',
};
await writeFile(resolve(values.output, 'summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
