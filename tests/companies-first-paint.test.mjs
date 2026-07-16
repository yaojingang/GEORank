import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

const defaultProjectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const projectRoot = path.resolve(process.env.GEORANK_PROJECT_ROOT || defaultProjectRoot);
const companiesDocumentPath = path.join(projectRoot, 'dist', 'index.html');
const companiesTailwindPath = path.join(projectRoot, 'dist', 'css', 'index-tailwind.css');
const sharedFrontendScriptPath = path.join(projectRoot, 'dist', 'js', 'common.js');

test('the companies page ships final Tailwind styles before first paint', async () => {
  const [html, css] = await Promise.all([
    readFile(companiesDocumentPath, 'utf8'),
    readFile(companiesTailwindPath, 'utf8')
  ]);

  assert.doesNotMatch(html, /cdn\.tailwindcss\.com|\/js\/tailwind\.config\.js/);
  assert.match(html, /<link\b[^>]*href="\/css\/index-tailwind\.css\?v=20260716-first-paint"/);
  assert.match(css, /\.bg-primary\{/);
  assert.match(css, /\.lg\\:grid-cols-12\{/);
  assert.match(css, /\.lg\\:col-span-8\{/);
});

test('site settings keep server-rendered copy until hydration finishes', async () => {
  const source = await readFile(sharedFrontendScriptPath, 'utf8');

  assert.match(
    source,
    /apply\(root = document\)\s*\{[\s\S]*?if \(!this\.state\.loaded\) return;[\s\S]*?const settings = this\.settings;/
  );
});
