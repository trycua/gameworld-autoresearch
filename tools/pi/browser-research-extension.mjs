import { runBrowserResearch } from './browser-research.mjs';

export default function (pi) {
  let active;
  let task;
  for (const mode of ['browser', 'hybrid']) {
    pi.registerCommand(`${mode}-research`, {
      description: `${mode === 'browser' ? 'Browser-only' : 'SearXNG plus browser'} source-checked research with isolated workers`,
      async handler(question, ctx) {
        if (active) { ctx.ui.notify('A browser research run is already active. Use /research-stop first.', 'warning'); return; }
        if (!question.trim()) { ctx.ui.notify(`Usage: /${mode}-research <question>`, 'warning'); return; }
        const controller = new AbortController();
        active = controller;
        ctx.ui.notify(`Starting ${mode} research. Use /research-stop to cancel.`, 'info');
        task = runBrowserResearch({ question, mode, signal: controller.signal, modelRegistry: ctx.modelRegistry,
          onPhase: (phase) => ctx.ui.setStatus('browser-research', `${mode}: ${phase}`),
        }).then(async ({ directory, result }) => {
          await pi.sendMessage({ customType: 'gameworld-browser-research', content: JSON.stringify({ directory, result }), display: true });
        }).catch((error) => ctx.ui.notify(`Research stopped/failed: ${error.message}`, 'error'))
          .finally(() => { active = undefined; ctx.ui.setStatus('browser-research', undefined); });
      },
    });
  }
  pi.registerCommand('research-stop', {
    description: 'Cancel the current browser/hybrid research run and release its browsers',
    async handler(_args, ctx) {
      active?.abort();
      ctx.ui.notify(active ? 'Cancellation requested.' : 'No browser research run is active.', 'info');
    },
  });
  pi.on('session_shutdown', async () => { active?.abort(); await task; });
}
