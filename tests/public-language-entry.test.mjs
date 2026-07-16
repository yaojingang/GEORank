import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

async function read(relativePath) {
  return readFile(path.join(projectRoot, relativePath), 'utf8');
}

test('Next public pages expose locale switching while the legacy static shell stays Chinese-first', async () => {
  const [siteHeader, activeHomepage, legacyHeader, legacyRuntime, legacyStyles, adminSidebar, routing] = await Promise.all([
    read('packages/ui/src/layout/site-header.tsx'),
    read('runtime/homepages/public/active/index.html'),
    read('dist/components/header.html'),
    read('dist/js/common.js'),
    read('dist/css/common.css'),
    read('packages/ui/src/layout/admin-sidebar.tsx'),
    read('packages/i18n/src/routing.ts')
  ]);

  assert.match(siteHeader, /<LanguageSwitcher locale=\{locale\} variant="site" \/>/);
  assert.doesNotMatch(activeHomepage, /georank-language-switch|账号与语言|>EN<|>中</);
  assert.match(activeHomepage, /class="georank-header-actions" aria-label="账号"/);
  assert.doesNotMatch(legacyHeader, /data-language-switcher|data-lang-option|header-language/);
  assert.doesNotMatch(legacyRuntime, /data-language-switcher|data-lang-option|header-language/);
  assert.doesNotMatch(legacyStyles, /\.header-language/);
  assert.match(adminSidebar, /<LanguageSwitcher locale=\{locale\} variant="admin" \/>/);
  assert.match(routing, /export const defaultLocale = 'zh-CN';/);
});
