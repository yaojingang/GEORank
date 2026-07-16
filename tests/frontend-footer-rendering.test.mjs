import assert from 'node:assert/strict';
import {readdir, readFile} from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const copyrightText = '© 2026 GEORankHub · 公益性 GEO 研究平台 · 独立第三方 · GitHub开源';
const githubHref = 'https://github.com/yaojingang/GEORank';
const oldCopyrightPattern = /© 2024-2026 GEOrank|All rights reserved|footer\.rights/;

const stripMarkup = (html) => html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();

test('shared frontend footer keeps one fixed linked copyright', async () => {
  const [component, commonScript] = await Promise.all([
    readFile(path.join(projectRoot, 'dist', 'components', 'footer.html'), 'utf8'),
    readFile(path.join(projectRoot, 'dist', 'js', 'common.js'), 'utf8')
  ]);

  for (const [surface, source] of [['component', component], ['fallback', commonScript]]) {
    assert.match(source, /data-footer-rights/, surface);
    assert.match(source, new RegExp(`href="${githubHref}"`), surface);
    assert.match(source, /target="_blank" rel="noopener noreferrer"/, surface);
    assert.match(source, /<strong><a[^>]+>GitHub<\/a>开源<\/strong>/, surface);
    assert.ok(stripMarkup(source).includes(copyrightText), surface);
    assert.doesNotMatch(source, oldCopyrightPattern, surface);
  }
});

test('every static frontend page mounts the shared footer loader', async () => {
  const distDir = path.join(projectRoot, 'dist');
  const htmlFiles = (await readdir(distDir)).filter((file) => file.endsWith('.html'));
  const footerPages = [];

  for (const file of htmlFiles) {
    const source = await readFile(path.join(distDir, file), 'utf8');
    if (!source.includes('id="footer-container"')) continue;
    footerPages.push(file);
    assert.match(source, /<script src="\/js\/common\.js\?v=[^"]+"><\/script>/, file);
  }

  assert.equal(footerPages.length, 13);
});

test('custom homepage source and published mirrors use the same copyright', async () => {
  const files = [
    'runtime/homepages/public/active/index.html',
    'runtime/homepages/public/releases/f7e16e7c-e1aa-4e39-951b-4c274dd05175/index.html',
    'runtime/homepages/releases/f7e16e7c-e1aa-4e39-951b-4c274dd05175/source/index.html'
  ];

  for (const file of files) {
    const source = await readFile(path.join(projectRoot, file), 'utf8');
    assert.ok(stripMarkup(source).includes(copyrightText), file);
    assert.match(source, new RegExp(`href="${githubHref}"`), file);
    assert.match(source, /<strong><a[^>]+>GitHub<\/a>开源<\/strong>/, file);
    assert.doesNotMatch(source, oldCopyrightPattern, file);
  }
});
