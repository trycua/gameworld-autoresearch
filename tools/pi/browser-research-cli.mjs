import { parseArgs } from 'node:util';
import { runBrowserResearch } from './browser-research.mjs';

const { values } = parseArgs({ options: {
  mode: { type: 'string', default: 'hybrid' }, question: { type: 'string' },
  angles: { type: 'string', default: '1' }, output: { type: 'string' },
} });
const controller = new AbortController();
for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => controller.abort());
try {
  const result = await runBrowserResearch({ ...values, angles: Number(values.angles), signal: controller.signal,
    onPhase: (phase) => console.error(`Phase: ${phase}`),
  });
  console.log(JSON.stringify(result, null, 2));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
