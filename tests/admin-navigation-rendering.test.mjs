import assert from 'node:assert/strict';
import {readdir, readFile} from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const adminHtmlDir = path.join(projectRoot, 'dist', 'admin');
const adminCssPath = path.join(projectRoot, 'dist', 'css', 'admin.css');
const adminJsPath = path.join(projectRoot, 'dist', 'js', 'admin.js');
const nextAdminCssPath = path.join(projectRoot, 'apps', 'admin', 'app', 'globals.css');
const nextHomepagePath = path.join(
  projectRoot,
  'apps',
  'admin',
  'components',
  'homepage',
  'admin-homepage.tsx'
);

test('every static admin page paints without a whole-document opacity gate', async () => {
  const htmlFiles = (await readdir(adminHtmlDir)).filter((file) => file.endsWith('.html')).sort();
  const javascript = await readFile(adminJsPath, 'utf8');

  assert.ok(htmlFiles.length >= 12, `expected the admin page set, found ${htmlFiles.length}`);
  for (const file of htmlFiles) {
    const html = await readFile(path.join(adminHtmlDir, file), 'utf8');
    assert.doesNotMatch(html, /\bbody\s*\{[^}]*\bopacity\s*:\s*0(?:\.0+)?\s*(?:!important)?\s*;?/is, file);
  }
  assert.doesNotMatch(javascript, /document\.body\.style\.(?:opacity|transition)\s*=/);
});

test('static admin navigation keeps a stable shell while the next document initializes', async () => {
  const css = await readFile(adminCssPath, 'utf8');

  assert.match(css, /@view-transition\s*\{[^}]*navigation:\s*auto/s);
  assert.match(css, /#admin-topbar\s*\{[^}]*min-height:\s*4rem/s);
  assert.match(css, /#admin-sidebar\s*\{[^}]*background:\s*#fff/s);
});

test('every static admin page mounts the shared shell before parsing visible main content', async () => {
  const htmlFiles = (await readdir(adminHtmlDir)).filter((file) => file.endsWith('.html')).sort();

  for (const file of htmlFiles) {
    const html = await readFile(path.join(adminHtmlDir, file), 'utf8');
    const topbarIndex = html.indexOf('<div id="admin-topbar"></div>');
    const scriptPattern = /<script src="\.\.\/js\/admin\.js\?v=[^"]+"><\/script>/g;
    const scriptMatches = html.match(scriptPattern) || [];
    const scriptIndex = html.search(scriptPattern);
    const contentIndex = html.search(/<(?:main\b|div class="admin-editor-topbar\b)/);

    assert.ok(topbarIndex >= 0, `${file}: missing admin topbar mount`);
    assert.equal(scriptMatches.length, 1, `${file}: expected exactly one admin.js entrypoint`);
    assert.ok(scriptIndex > topbarIndex, `${file}: admin.js must run after the shell mounts exist`);
    assert.ok(contentIndex > scriptIndex, `${file}: admin.js must mount the shell before main content parses`);
  }
});

test('shared admin script mounts the complete shell before asynchronous hydration', async () => {
  const javascript = await readFile(adminJsPath, 'utf8');
  const sidebar = {innerHTML: ''};
  const topbar = {innerHTML: ''};
  const listeners = new Map();

  vm.runInNewContext(javascript, {
    URL,
    URLSearchParams,
    console,
    document: {
      readyState: 'loading',
      addEventListener(type, listener) {
        listeners.set(type, listener);
      },
      getElementById(id) {
        if (id === 'admin-sidebar') return sidebar;
        if (id === 'admin-topbar') return topbar;
        return null;
      },
      querySelectorAll() {
        return [];
      },
    },
    localStorage: {
      getItem() { return null; },
      setItem() {},
      removeItem() {},
    },
    window: {
      location: {
        href: 'https://example.com/admin/users',
        hostname: 'example.com',
        origin: 'https://example.com',
        pathname: '/admin/users',
        port: '',
        protocol: 'https:',
        search: '',
      },
    },
  });

  assert.match(sidebar.innerHTML, /GEOrank/);
  assert.match(sidebar.innerHTML, /仪表盘/);
  assert.match(sidebar.innerHTML, /用户管理/);
  assert.match(sidebar.innerHTML, /系统设置/);
  assert.match(sidebar.innerHTML, /正在验证管理员/);
  assert.doesNotMatch(sidebar.innerHTML, /id="logout-btn"/);
  assert.match(topbar.innerHTML, /用户管理/);
  assert.ok(listeners.has('DOMContentLoaded'));
});

test('deployed homepage settings exposes a guarded HTML source editor', async () => {
  const settingsHtml = await readFile(path.join(adminHtmlDir, 'settings.html'), 'utf8');
  const javascript = await readFile(adminJsPath, 'utf8');

  assert.match(settingsHtml, /homepage-release-list/);
  assert.match(javascript, /data-homepage-edit/);
  assert.match(javascript, /data-homepage-clone/);
  assert.match(javascript, /\/homepage\/releases\/\$\{[^}]+\}\/source/);
  assert.match(javascript, /\/homepage\/releases\/\$\{[^}]+\}\/clone/);
  assert.match(javascript, /openHomepageSourceEditor\(created\.id\)/);
  assert.match(javascript, /method:\s*['"]PUT['"]|api\(['"]PUT['"]/);
  assert.match(javascript, /expected_sha256/);
  assert.match(javascript, /editorSaveLabel\s*=\s*release\.status\s*===\s*['"]active['"]/);
  assert.match(javascript, /(?:ctrlKey|metaKey)[\s\S]{0,160}key\.toLowerCase\(\)\s*===\s*['"]s['"]/);
  assert.match(javascript, /beforeunload/);
});

test('next homepage clone opens the editor without a state-reset race', async () => {
  const component = await readFile(nextHomepagePath, 'utf8');

  assert.match(component, /const pendingEditorIdRef = useRef\(['"]['"]\)/);
  assert.doesNotMatch(component, /\[pendingEditorId,\s*setPendingEditorId\]\s*=\s*useState/);
  assert.match(
    component,
    /pendingEditorIdRef\.current\s*&&\s*pendingEditorIdRef\.current\s*===\s*selectedId/
  );
  assert.match(
    component,
    /pendingEditorIdRef\.current\s*=\s*created\.id;[\s\S]{0,160}await loadHomepage\(created\.id\)/
  );
});

test('next homepage editor guards unsaved work and shows cloned release size', async () => {
  const component = await readFile(nextHomepagePath, 'utf8');

  assert.match(component, /addEventListener\(['"]beforeunload['"]/);
  assert.match(component, /function confirmDiscardEditorChanges\(\)/);
  assert.match(component, /function handleSelectRelease\(releaseId: string\)/);
  assert.match(component, /onClick=\{\(\) => handleSelectRelease\(release\.id\)\}/);
  assert.match(component, /formatBytes\(release\.extracted_size \|\| release\.compressed_size\)/);
});

test('static user directory exposes profile editing and direct admin password reset', async () => {
  const javascript = await readFile(adminJsPath, 'utf8');
  const editorStart = javascript.indexOf('async function openUserEditModal(userId)');
  const editorEnd = javascript.indexOf('async function loadUsers()', editorStart);

  assert.ok(editorStart >= 0, 'missing the user editor');
  assert.ok(editorEnd > editorStart, 'could not isolate the user editor');

  const editor = javascript.slice(editorStart, editorEnd);
  assert.match(javascript, /class="btn-edit-user[^"\n]*"/);
  assert.match(editor, /api\('GET', `\/api\/admin\/users\/\$\{userId\}`\)/);
  assert.match(editor, /name="username"/);
  assert.match(editor, /name="email"/);
  assert.match(editor, /name="phone"/);
  assert.match(editor, /api\('PUT', `\/api\/admin\/users\/\$\{userId\}`, payload\)/);
  assert.match(editor, /name="new_password"/);
  assert.match(editor, /name="confirm_password"/);
  assert.match(
    editor,
    /api\('PUT', `\/api\/admin\/users\/\$\{userId\}\/password`, \{ password: newPassword \}\)/
  );
  assert.doesNotMatch(editor, /current_password|原密码/);
});

test('homepage file pickers use the admin button visual language', async () => {
  const settingsHtml = await readFile(path.join(adminHtmlDir, 'settings.html'), 'utf8');
  const css = await readFile(adminCssPath, 'utf8');
  const nextCss = await readFile(nextAdminCssPath, 'utf8');
  const component = await readFile(nextHomepagePath, 'utf8');

  assert.match(settingsHtml, /homepage-file-input/);
  assert.match(component, /className="admin-input homepage-file-input"/);
  assert.match(css, /\.homepage-file-input::file-selector-button/);
  assert.match(nextCss, /\.homepage-file-input::file-selector-button/);
});
