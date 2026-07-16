import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

async function read(relativePath) {
  return readFile(path.join(projectRoot, relativePath), 'utf8');
}

test('admin settings exposes an ordered navigation menu editor', async () => {
  const [html, script, css] = await Promise.all([
    read('dist/admin/settings.html'),
    read('dist/js/admin.js'),
    read('dist/css/admin.css')
  ]);

  assert.match(html, /id="navigation-menu-list"/);
  assert.match(html, /id="navigation-menu-add"/);
  assert.match(html, /id="navigation-menu-save"/);
  assert.match(script, /navigation_menu:\s*\{\s*value:\s*\{items/);
  assert.match(script, /is_public:\s*true/);
  assert.match(script, /const target\s*=\s*targetValue\s*===\s*'_self'\s*\?\s*'_self'\s*:\s*'_blank'/);
  assert.match(script, /target:\s*'_blank',\s*enabled:\s*true/);
  assert.match(script, /新标签页（默认）/);
  assert.match(css, /--navigation-menu-control-height:\s*2\.75rem/);
  assert.match(css, /--navigation-menu-select-font-size:\s*0\.8125rem/);
  assert.match(css, /#navigation-menu-list \.form-input\s*\{[^}]*box-sizing:\s*border-box[^}]*height:\s*var\(--navigation-menu-control-height\)[^}]*min-height:\s*var\(--navigation-menu-control-height\)/s);
  assert.match(css, /#navigation-menu-list \[data-navigation-menu-target\]\s*\{[^}]*font-size:\s*var\(--navigation-menu-select-font-size\)/s);
});

test('shared static pages render configured labels, URLs, and opening targets safely', async () => {
  const [script, header] = await Promise.all([
    read('dist/js/common.js'),
    read('dist/components/header.html')
  ]);

  assert.match(script, /navigation_menu:\s*this\.normalizeNavigationMenu\(payload\?\.navigation_menu\)/);
  assert.match(script, /link\.textContent\s*=\s*item\.label/);
  assert.match(script, /link\.setAttribute\('target',\s*item\.target\)/);
  assert.match(script, /link\.setAttribute\('rel',\s*'noopener noreferrer'\)/);

  const fallbackHeader = script.match(/const HEADER_HTML = `([\s\S]*?)`;\n\nconst FOOTER_HTML/)?.[1] || '';
  assert.equal((fallbackHeader.match(/data-site-navigation/g) || []).length, 2);
  assert.equal((header.match(/data-site-navigation/g) || []).length, 2);
});

test('custom homepage loads the trusted navigation runtime', async () => {
  const [runtime, activeHomepage] = await Promise.all([
    read('dist/js/site-navigation.js'),
    read('runtime/homepages/public/releases/9fe4a087-42bc-423a-bc59-fc020018a6f9/index.html')
  ]);

  assert.match(runtime, /api\/settings\/public/);
  assert.match(runtime, /document\.createElement\('a'\)/);
  assert.match(runtime, /link\.textContent\s*=\s*item\.label/);
  assert.match(activeHomepage, /data-georank-navigation-runtime/);
  assert.match(activeHomepage, /src="\/js\/site-navigation\.js"/);
});
