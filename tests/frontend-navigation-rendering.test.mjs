import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const frontendHtmlDir = path.join(projectRoot, 'dist');
const sharedFrontendScriptPath = path.join(projectRoot, 'dist', 'js', 'common.js');
const sharedFrontendCssPath = path.join(projectRoot, 'dist', 'css', 'common.css');
const sharedHeaderPath = path.join(projectRoot, 'dist', 'components', 'header.html');
const companiesDocumentPath = path.join(projectRoot, 'dist', 'index.html');
const solutionsDocumentPath = path.join(projectRoot, 'dist', 'solutions.html');
const sharedTailwindPath = path.join(projectRoot, 'dist', 'css', 'public-tailwind.css');
const navigationPaintAssetVersion = '20260716-first-paint-lifecycle';
const moduleControllerAssetVersion = navigationPaintAssetVersion;
const publicStaticFrontendFiles = [
  'company-submit.html',
  'company.html',
  'diagnostic.html',
  'experts.html',
  'index.html',
  'keywords.html',
  'login.html',
  'plans.html',
  'profile.html',
  'register.html',
  'solutions.html',
  'tools.html',
  'tutorial.html'
];
const moduleControllerPaths = [
  'company-submit-page.js',
  'company.js',
  'diagnostic.js',
  'experts.js',
  'index.js',
  'keywords.js',
  'plans.js',
  'solutions.js',
  'submit-company.js',
  'tools.js',
  'tutorial.js'
].map((file) => path.join(projectRoot, 'dist', 'js', file));
const serverRenderedFrontendPaths = [
  path.join(projectRoot, 'backend', 'app', 'web', 'company_pages.py'),
  path.join(projectRoot, 'backend', 'app', 'web', 'tutorial_pages.py')
];

test('every static frontend page paints without a whole-document opacity gate', async () => {
  const htmlFiles = publicStaticFrontendFiles;

  assert.equal(htmlFiles.length, 13);
  for (const file of htmlFiles) {
    const html = await readFile(path.join(frontendHtmlDir, file), 'utf8');
    assert.doesNotMatch(
      html,
      /(?:\bbody\s*\{[^}]*\bopacity\s*:\s*0(?:\.0+)?|<body\b[^>]*\bstyle=["'][^"']*\bopacity\s*:\s*0(?:\.0+)?)/is,
      file
    );
  }
});

test('server-rendered frontend templates paint without a whole-document opacity gate', async () => {
  for (const templatePath of serverRenderedFrontendPaths) {
    const source = await readFile(templatePath, 'utf8');
    assert.doesNotMatch(
      source,
      /body\{\{opacity:0(?:\.0+)?|document\.body\.style\.(?:opacity|transition)\s*=/,
      path.relative(projectRoot, templatePath)
    );
  }
});

test('all frontend documents request the navigation paint fix with one fresh asset version', async () => {
  const htmlFiles = publicStaticFrontendFiles;
  const documentPaths = [
    ...htmlFiles.map((file) => path.join(frontendHtmlDir, file)),
    ...serverRenderedFrontendPaths
  ];

  for (const documentPath of documentPaths) {
    const source = await readFile(documentPath, 'utf8');
    assert.match(
      source,
      new RegExp(`/css/common\\.css\\?v=${navigationPaintAssetVersion}`),
      `${path.relative(projectRoot, documentPath)} common.css`
    );
    assert.match(
      source,
      new RegExp(`/js/common\\.js\\?v=${navigationPaintAssetVersion}`),
      `${path.relative(projectRoot, documentPath)} common.js`
    );
  }
});

test('Tailwind runtime dependencies do not block body parsing', async () => {
  const htmlFiles = publicStaticFrontendFiles;
  const documentPaths = [
    ...htmlFiles.map((file) => path.join(frontendHtmlDir, file)),
    ...serverRenderedFrontendPaths
  ];

  for (const documentPath of documentPaths) {
    const source = await readFile(documentPath, 'utf8');
    const tailwindScripts = [...source.matchAll(/<script\b[^>]*\bsrc=["'][^"']*tailwind[^"']*["'][^>]*>/gi)];
    for (const [tag] of tailwindScripts) {
      assert.match(tag, /\bdefer\b/i, `${path.relative(projectRoot, documentPath)}: ${tag}`);
    }
  }
});

test('frontend documents ship Tailwind styles locally before first paint', async () => {
  const htmlFiles = publicStaticFrontendFiles;
  const documentPaths = [
    ...htmlFiles.map((file) => path.join(frontendHtmlDir, file)),
    ...serverRenderedFrontendPaths
  ];
  const css = await readFile(sharedTailwindPath, 'utf8');

  assert.match(css, /\.bg-primary\{/);
  assert.match(css, /\.md\\:flex\{/);
  assert.match(css, /\.max-w-5xl\{/);

  for (const documentPath of documentPaths) {
    const source = await readFile(documentPath, 'utf8');
    assert.doesNotMatch(
      source,
      /cdn\.tailwindcss\.com|\/js\/tailwind\.config\.js/,
      path.relative(projectRoot, documentPath)
    );
    if (documentPath === companiesDocumentPath) {
      assert.match(source, /\/css\/index-tailwind\.css\?v=20260716-first-paint/);
      continue;
    }
    assert.match(
      source,
      /\/css\/public-tailwind\.css\?v=20260716-first-paint-lifecycle/,
      path.relative(projectRoot, documentPath)
    );
  }
});

test('external font styles avoid a late glyph swap on the solutions workspace', async () => {
  const htmlFiles = publicStaticFrontendFiles;
  const documentPaths = [
    ...htmlFiles.map((file) => path.join(frontendHtmlDir, file)),
    ...serverRenderedFrontendPaths
  ];

  for (const documentPath of documentPaths) {
    const source = await readFile(documentPath, 'utf8');
    const fontStyles = [...source.matchAll(/<link\b[^>]*\bhref=["']https:\/\/fonts\.googleapis\.com\/css2[^"']*["'][^>]*>/gi)];
    for (const [tag] of fontStyles) {
      if (documentPath === solutionsDocumentPath) {
        assert.doesNotMatch(tag, /\bmedia=["']print["']/i, `${path.relative(projectRoot, documentPath)}: ${tag}`);
        assert.doesNotMatch(tag, /\bonload=/i, `${path.relative(projectRoot, documentPath)}: ${tag}`);
        continue;
      }
      assert.match(tag, /\bmedia=["']print["']/i, `${path.relative(projectRoot, documentPath)}: ${tag}`);
      assert.match(tag, /\bonload=["']this\.media='all'["']/i, `${path.relative(projectRoot, documentPath)}: ${tag}`);
    }
  }
});

test('module controller documents request one fresh lifecycle version', async () => {
  const htmlFiles = publicStaticFrontendFiles;
  const documentPaths = [
    ...htmlFiles.map((file) => path.join(frontendHtmlDir, file)),
    ...serverRenderedFrontendPaths
  ];
  const controllerPattern = new RegExp(
    `<script\\b[^>]*\\bsrc=["']/js/(?:${moduleControllerPaths.map((file) => path.basename(file, '.js')).join('|')})\\.js\\?v=([^"']+)["'][^>]*>`,
    'g'
  );

  for (const documentPath of documentPaths) {
    const source = await readFile(documentPath, 'utf8');
    for (const match of source.matchAll(controllerPattern)) {
      assert.equal(
        match[1],
        moduleControllerAssetVersion,
        `${path.relative(projectRoot, documentPath)}: ${match[0]}`
      );
    }
  }

  const referencedControllers = new Set();
  for (const documentPath of documentPaths) {
    const source = await readFile(documentPath, 'utf8');
    for (const controllerPath of moduleControllerPaths) {
      if (source.includes(`/js/${path.basename(controllerPath)}?v=${moduleControllerAssetVersion}`)) {
        referencedControllers.add(path.basename(controllerPath));
      }
    }
  }
  assert.deepEqual(referencedControllers, new Set(moduleControllerPaths.map((file) => path.basename(file))));
});

test('the shared frontend shell mounts before asynchronous configuration hydration', async () => {
  const source = await readFile(sharedFrontendScriptPath, 'utf8');
  const mountCall = source.indexOf('ComponentLoader.mountFallbacks();');
  const domReadyListener = source.lastIndexOf("document.addEventListener('DOMContentLoaded'");

  assert.ok(mountCall >= 0, 'expected the inline header/footer shell to mount synchronously');
  assert.ok(mountCall < domReadyListener, 'expected the inline shell before DOMContentLoaded hydration');
  assert.doesNotMatch(source, /document\.body\.style\.(?:opacity|transition)\s*=/);
  assert.doesNotMatch(source, /document\.addEventListener\('DOMContentLoaded',\s*async/);
  assert.match(source, /void Promise\.allSettled\(shellLoads\)/);
  assert.doesNotMatch(source, /Promise\.all\([^)]*ModuleGate\.load/);
  assert.match(
    source,
    /void PageLifecycle\.run\(\(\) => \{[\s\S]*?Voting\.init\(\);[\s\S]*?Search\.init\(\);[\s\S]*?\}\);/
  );
});

test('new frontend JavaScript reveals a legacy cached transparent document before hydration', async () => {
  const source = await readFile(sharedFrontendScriptPath, 'utf8');
  const revealCall = source.indexOf('ComponentLoader.revealLegacyDocument();');
  const domReadyListener = source.lastIndexOf("document.addEventListener('DOMContentLoaded'");

  assert.ok(revealCall >= 0, 'expected a JavaScript compatibility reveal for cached HTML and CSS');
  assert.ok(revealCall < domReadyListener, 'expected the compatibility reveal before async hydration');
  assert.match(
    source,
    /revealLegacyDocument\(\)\s*\{[\s\S]*?getComputedStyle\(body\)\.opacity[\s\S]*?body\.style\.opacity\s*=\s*'1'[\s\S]*?body\.style\.transition\s*=\s*'none'/
  );
});

test('the immediate header is complete before asynchronous configuration loads', async () => {
  const [source, header] = await Promise.all([
    readFile(sharedFrontendScriptPath, 'utf8'),
    readFile(sharedHeaderPath, 'utf8')
  ]);
  const inlineHeader = source.match(/const HEADER_HTML = `([\s\S]*?)`;/)?.[1] || '';

  assert.ok(inlineHeader, 'expected a complete immediate header');
  assert.match(inlineHeader, /<nav\b[^>]*id="main-nav"/);
  assert.match(inlineHeader, /data-nav-link/);
  assert.match(inlineHeader, /data-auth-trigger/);
  assert.match(inlineHeader, /id="mobile-menu-toggle"/);
  assert.match(inlineHeader, /data-navigation-item="github"/);
  assert.match(header, /data-navigation-item="github"/);
  assert.doesNotMatch(source, /HEADER_SHELL_HTML/);
  assert.match(
    source,
    /mountFallbacks\(\)\s*\{[\s\S]*?header\.innerHTML\s*=\s*HEADER_HTML/
  );
  assert.match(
    source,
    /loadHeader\(\)\s*\{[\s\S]*?header\?\.querySelector\('#main-nav'\)[\s\S]*?this\.load\('\/components\/header\.html'/
  );
});

test('first-frame header controls render without external icon fonts', async () => {
  const [source, sharedHeader, solutionsDocument] = await Promise.all([
    readFile(sharedFrontendScriptPath, 'utf8'),
    readFile(sharedHeaderPath, 'utf8'),
    readFile(solutionsDocumentPath, 'utf8')
  ]);
  const inlineHeader = source.match(/const HEADER_HTML = `([\s\S]*?)`;/)?.[1] || '';
  const solutionsHeader = solutionsDocument.match(
    /<div id="header-container"[^>]*>([\s\S]*?)<\/div>\s*\n\s*<!-- Main Container -->/
  )?.[1] || '';

  for (const [label, header] of [
    ['inline header', inlineHeader],
    ['shared header', sharedHeader],
    ['solutions header', solutionsHeader]
  ]) {
    assert.equal([...header.matchAll(/<svg\b/g)].length, 2, label);
    assert.doesNotMatch(
      header,
      /class="material-symbols-outlined[^>]*">\s*(?:person|menu)\s*</,
      label
    );
  }
});

test('module configuration updates the visible header independently of component hydration', async () => {
  const source = await readFile(sharedFrontendScriptPath, 'utf8');

  assert.match(
    source,
    /whenAvailable\(\)\s*\{[\s\S]*?ModuleGate\.load\(\)[\s\S]*?ModuleGate\.applyHeader\(\);[\s\S]*?ModuleGate\.guardCurrentPage\(\)/
  );
});

test('the fetched header becomes interactive before module configuration resolves', async () => {
  const source = await readFile(sharedFrontendScriptPath, 'utf8');
  const loadHeader = source.match(/async loadHeader\(\)\s*\{([\s\S]*?)\n\s*\},/)?.[1] || '';

  assert.ok(loadHeader, 'expected the shared header hydration method');
  assert.ok(
    loadHeader.indexOf('Navigation.init();') < loadHeader.indexOf('await ModuleGate.load();'),
    'expected navigation binding before the module configuration request'
  );
});

test('module page controllers wait for the shared availability contract', async () => {
  const commonSource = await readFile(sharedFrontendScriptPath, 'utf8');

  assert.match(commonSource, /const PageLifecycle\s*=\s*\{/);
  assert.match(commonSource, /run\(callback\)\s*\{[\s\S]*?whenAvailable\(\)/);
  assert.match(commonSource, /new CustomEvent\('georank:page-available'/);

  for (const controllerPath of moduleControllerPaths) {
    const source = await readFile(controllerPath, 'utf8');
    assert.match(
      source,
      /PageLifecycle\?\.run\?\.bind\([^)]+\)\s*\|\|\s*\(\(callback\)\s*=>\s*callback\(\)\)/,
      path.relative(projectRoot, controllerPath)
    );
    assert.doesNotMatch(source, /DOMContentLoaded/, path.relative(projectRoot, controllerPath));
  }
});

test('shared hydration can start before deferred third-party scripts finish', async () => {
  const source = await readFile(sharedFrontendScriptPath, 'utf8');

  assert.match(
    source,
    /whenDomReady\(\)\s*\{[\s\S]*?document\.body\s*&&\s*document\.querySelector\('main'\)[\s\S]*?Promise\.resolve\(\)/
  );
  assert.match(source, /function initializeFrontend\(\)/);
  assert.match(
    source,
    /if \(document\.body\)\s*\{[\s\S]*?initializeFrontend\(\);[\s\S]*?\}\s*else\s*\{[\s\S]*?DOMContentLoaded/
  );
});

test('the profile controller can initialize before deferred Tailwind completes', async () => {
  const [source, html] = await Promise.all([
    readFile(path.join(projectRoot, 'dist', 'js', 'profile.js'), 'utf8'),
    readFile(path.join(projectRoot, 'dist', 'profile.html'), 'utf8')
  ]);

  assert.match(source, /async function initProfile\(\)/);
  assert.match(html, /\/js\/profile\.js\?v=20260716-first-paint-lifecycle/);
  assert.match(
    source,
    /if \(document\.body\)\s*\{[\s\S]*?void initProfile\(\);[\s\S]*?\}\s*else\s*\{[\s\S]*?DOMContentLoaded/
  );
});

test('component hydration has a bounded fallback and reports failures', async () => {
  const source = await readFile(sharedFrontendScriptPath, 'utf8');

  assert.match(source, /const COMPONENT_LOAD_TIMEOUT_MS\s*=\s*2500/);
  assert.match(
    source,
    /async load\([^)]*\)\s*\{[\s\S]*?new AbortController\(\)[\s\S]*?controller\.abort\(\)[\s\S]*?fetch\(url,\s*\{[\s\S]*?signal:\s*controller\.signal/
  );
  assert.match(source, /console\.warn\('\[GEOrank\] component load failed; using fallback'/);
  assert.match(source, /window\.clearTimeout\(timeout\)/);
});

test('shell hydration reports downstream initialization failures', async () => {
  const source = await readFile(sharedFrontendScriptPath, 'utf8');

  assert.match(
    source,
    /Promise\.allSettled\(shellLoads\)\.then\(results => \{[\s\S]*?result\.status !== 'rejected'[\s\S]*?console\.warn\('\[GEOrank\] shell hydration failed'/
  );
});

test('the inline and fetched headers share the signed-out authentication destination', async () => {
  const [source, header] = await Promise.all([
    readFile(sharedFrontendScriptPath, 'utf8'),
    readFile(sharedHeaderPath, 'utf8')
  ]);
  const inlineHeader = source.match(/const HEADER_HTML = `([\s\S]*?)`;/)?.[1] || '';
  const navigationContract = (html) => [...html.matchAll(
    /<a\s+href="([^"]+)"\s+data-nav-link\s+data-i18n="([^"]+)"/g
  )].map((match) => `${match[2]}:${match[1]}`);

  assert.ok(inlineHeader, 'expected the full offline header fallback');
  assert.deepEqual(navigationContract(inlineHeader), navigationContract(header));
  assert.match(inlineHeader, /href="\/login"\s+data-auth-trigger\s+data-profile-link/);
  assert.match(header, /href="\/login"[\s\S]{0,120}data-auth-trigger[\s\S]{0,120}data-profile-link/);
  assert.match(inlineHeader, /id="mobile-menu-toggle"/);
  assert.match(header, /id="mobile-menu-toggle"/);
});

test('shared frontend styles keep legacy cached documents visible without disabling body transitions globally', async () => {
  const css = await readFile(sharedFrontendCssPath, 'utf8');

  assert.match(css, /html\s+body\s*\{[^}]*opacity:\s*1\s*!important/s);
  assert.doesNotMatch(css, /html\s+body\s*\{[^}]*transition:\s*none\s*!important/s);
});
