import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { workflowProjectPaths } from './node_modules/@quintinshaw/pi-dynamic-workflows/dist/workflow-paths.js';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const agentDir = resolve(root, '.pi-local/agent');
const workflowPaths = workflowProjectPaths(root);
const packageDir = resolve(root, 'tools/pi/node_modules/@quintinshaw/pi-dynamic-workflows');
const settings = {
  defaultProvider: 'cua-litellm',
  defaultModel: 'gpt-5.6-sol',
  defaultThinkingLevel: 'medium',
  packages: [{ source: packageDir, extensions: [] }],
  extensions: [resolve(root, 'tools/pi/workflows.mjs'), resolve(root, 'tools/pi/research-routing.mjs'), resolve(root, 'tools/pi/browser-research-extension.mjs')],
  enabledModels: ['cua-litellm/*'],
};
const files = [
  [resolve(agentDir, 'settings.json'), `${JSON.stringify(settings, null, 2)}\n`],
  [resolve(agentDir, 'models.json'), await readFile(resolve(root, 'configs/pi/models.json'), 'utf8')],
  [resolve(agentDir, 'AGENTS.md'), await readFile(resolve(root, 'configs/pi/research-instructions.md'), 'utf8')],
  [workflowPaths.settingsPath, await readFile(resolve(root, 'configs/pi/workflow-settings.json'), 'utf8')],
  [workflowPaths.modelTiersPath, await readFile(resolve(root, 'configs/pi/model-tiers.json'), 'utf8')],
];
for (const [path, content] of files) {
  try {
    const existing = await readFile(path, 'utf8');
    if (existing !== content) throw new Error(`Refusing to overwrite modified configuration: ${path}`);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
}
for (const [path, content] of files) {
  await mkdir(dirname(path), { recursive: true, mode: 0o700 });
  await writeFile(path, content, { mode: 0o600 });
}
console.log(`Pi profile: ${agentDir}\nProject workflow configuration: ${workflowPaths.rootDir}`);
