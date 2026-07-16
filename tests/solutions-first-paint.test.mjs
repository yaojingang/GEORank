import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const solutionsDocumentPath = path.join(projectRoot, 'dist', 'solutions.html');
const solutionsControllerPath = path.join(projectRoot, 'dist', 'js', 'solutions.js');
const sharedFrontendScriptPath = path.join(projectRoot, 'dist', 'js', 'common.js');

test('the solutions workspace ships its visible first-frame modules in final form', async () => {
  const [source, controller] = await Promise.all([
    readFile(solutionsDocumentPath, 'utf8'),
    readFile(solutionsControllerPath, 'utf8')
  ]);
  const header = source.match(/<div id="header-container"[^>]*>([\s\S]*?)<\/div>\s*\n\s*<!-- Main Container -->/)?.[1] || '';
  const channelList = source.match(/<div id="solution-channel-list"[^>]*>([\s\S]*?)<\/div>\s*\n\s*<\/div>\s*\n\s*<div class="flex items-center justify-between border-t/)?.[1] || '';
  const channelButtons = [...channelList.matchAll(/data-solution-channel=/g)];
  const headScripts = [...source.matchAll(/<script\b[^>]*\bsrc=["']https:\/\/cdn\.jsdelivr\.net\/[^"']+["'][^>]*>/gi)];

  assert.match(header, /id="main-nav"/);
  assert.match(source, /id="header-container"\s+data-prerendered="true"/);
  assert.match(header, /data-nav-link/);
  assert.match(header, /data-auth-trigger/);
  assert.match(header, />GEORank<\/a>/);
  assert.match(header, /data-navigation-item="github"/);
  assert.match(header, /data-navigation-item="solutions"[^>]*text-blue-600/);
  assert.doesNotMatch(source, /fonts\.googleapis\.com\/css2\?family=Manrope/);
  assert.equal(channelButtons.length, 5);
  assert.doesNotMatch(source, /正在加载问答频道/);
  assert.match(source, /id="solution-active-channel-title"[^>]*>GEO 入门科普<\/h3>/);
  assert.match(source, /GEO 入门科普 1/);
  assert.match(source, /id="chat-context-badge"[^>]*>公开会话<\/span>/);
  assert.match(source, /当前支持公开问答会话。生成后会自动写入可分享的公开链接。/);
  for (const id of ['export-word-btn', 'export-pdf-btn', 'export-html-btn', 'feedback-helpful-btn', 'feedback-refine-btn']) {
    assert.match(source, new RegExp(`id="${id}"[^>]*\\bdisabled\\b`), id);
  }
  assert.match(source, /document\.documentElement\.classList\.add\('solutions-initializing'\)/);
  assert.match(controller, /function canReusePrerenderedFrame\(/);
  assert.match(controller, /if \(!reusePrerenderedFrame\)\s*\{[\s\S]*?renderChannels\(\);[\s\S]*?renderMessages\(\);/);
  for (const [tag] of headScripts) {
    assert.match(tag, /\bdefer\b/i, tag);
  }
});

test('the first-frame reuse decision is a pure, pinned invariant', async () => {
  const controller = await readFile(solutionsControllerPath, 'utf8');
  const functionSource = controller.match(/function canReusePrerenderedFrame\([\s\S]*?\n    \}/)?.[0] || '';
  const canReusePrerenderedFrame = Function(`${functionSource}; return canReusePrerenderedFrame;`)();
  const baseline = {
    isAuthenticated: false,
    currentConversationId: '',
    diagnosticReportId: '',
    companyId: '',
    sourceUrl: '',
    prompt: '',
    selectedChannelKey: 'geo-basics'
  };

  assert.equal(canReusePrerenderedFrame(baseline, false, 'geo-basics'), true);
  assert.equal(canReusePrerenderedFrame({...baseline, isAuthenticated: true}, false, 'geo-basics'), false);
  assert.equal(canReusePrerenderedFrame({...baseline, prompt: '解释 GEO'}, false, 'geo-basics'), false);
  assert.equal(canReusePrerenderedFrame({...baseline, selectedChannelKey: 'action-plan'}, false, 'geo-basics'), false);
  assert.equal(canReusePrerenderedFrame(baseline, true, 'geo-basics'), false);
});

test('conversation restore waits for deferred Markdown dependencies', async () => {
  const controller = await readFile(solutionsControllerPath, 'utf8');

  assert.match(
    controller,
    /function whenDeferredDependenciesReady\(\)[\s\S]*?window\.addEventListener\('load'[\s\S]*?async function loadConversation[\s\S]*?await whenDeferredDependenciesReady\(\)/
  );
});

test('rendered headers and matching navigation are preserved during hydration', async () => {
  const source = await readFile(sharedFrontendScriptPath, 'utf8');

  assert.match(
    source,
    /async loadHeader\(\)\s*\{[\s\S]*?header\?\.querySelector\('#main-nav'\)[\s\S]*?this\.load\('\/components\/header\.html'/
  );
  assert.match(
    source,
    /applyNavigation\(root = document\)\s*\{[\s\S]*?alreadyMatches[\s\S]*?if \(alreadyMatches\) return;/
  );
  assert.doesNotMatch(source, /I18N\.bindSwitcher\(\)/);
});
