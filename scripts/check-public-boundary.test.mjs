import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const checker = join(dirname(fileURLToPath(import.meta.url)), 'check-public-boundary.mjs');

function createRepo(files) {
  const root = mkdtempSync(join(tmpdir(), 'georank-public-boundary-'));
  execFileSync('git', ['init', '--quiet'], { cwd: root });
  for (const [path, content] of Object.entries(files)) {
    const absolutePath = join(root, path);
    mkdirSync(dirname(absolutePath), { recursive: true });
    writeFileSync(absolutePath, content);
  }
  execFileSync('git', ['add', '.'], { cwd: root });
  return root;
}

function createArchive(files) {
  const repository = createRepo(files);
  return createArchiveFromRepo(repository);
}

function createArchiveFromRepo(repository) {
  const parent = mkdtempSync(join(tmpdir(), 'georank-public-archive-'));
  const archivePath = join(parent, 'source.tar');
  const root = join(parent, 'source');
  mkdirSync(root);
  execFileSync('git', [
    '-c', 'user.name=GEORank Test',
    '-c', 'user.email=georank-test@example.invalid',
    'commit', '--quiet', '-m', 'fixture',
  ], { cwd: repository });
  execFileSync('git', ['archive', '--format=tar', `--output=${archivePath}`, 'HEAD'], {
    cwd: repository,
  });
  execFileSync('tar', ['-xf', archivePath, '-C', root]);
  rmSync(repository, { recursive: true, force: true });
  return { parent, root };
}

function writeUntracked(root, path, content) {
  const absolutePath = join(root, path);
  mkdirSync(dirname(absolutePath), { recursive: true });
  writeFileSync(absolutePath, content);
}

function runChecker(root, ...extraArguments) {
  return spawnSync(process.execPath, [checker, '--root', root, ...extraArguments], {
    cwd: root,
    encoding: 'utf8',
  });
}

function privateKeyHeader(prefix = '') {
  return ['-----BEGIN', prefix, 'PRIVATE', 'KEY-----'].filter(Boolean).join(' ');
}

function utf16BigEndian(value) {
  const buffer = Buffer.from(value, 'utf16le');
  for (let index = 0; index + 1 < buffer.length; index += 2) {
    [buffer[index], buffer[index + 1]] = [buffer[index + 1], buffer[index]];
  }
  return buffer;
}

test('accepts a safe source archive without Git metadata', (t) => {
  const { parent, root } = createArchive({
    'README.md': '# Safe public source archive\n',
    '.env.example': 'API_KEY=replace-me\n',
  });
  t.after(() => rmSync(parent, { recursive: true, force: true }));

  const result = runChecker(root);

  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /archive mode/);
});

test('archive mode rejects injected private paths and unsafe payloads', (t) => {
  const owner = ['AI', 'haoke'].join('');
  const repository = 'GEORank';
  const privateHost = ['example-team', 'feishu', 'cn'].join('.');
  const cases = [
    {
      path: 'docs/history/legacy.md',
      content: `https://github.com/${owner}/${repository}.git\n`,
      expected: /legacy repository reference/,
    },
    { path: 'private/.env', content: 'API_KEY=replace-me\n', expected: /forbidden path/ },
    {
      path: 'src/provider.ts',
      content: `const apiKey = "${'sk-live-' + 'S'.repeat(32)}";\n`,
      expected: /high-confidence secret/,
    },
    {
      path: 'config/nul-provider.yaml',
      content: Buffer.concat([
        Buffer.from(`api_key: ${'sk-live-' + 'N'.repeat(32)}`),
        Buffer.from([0]),
      ]),
      expected: /NUL byte|high-confidence secret/,
    },
    {
      path: 'docs/utf16-wiki.bin',
      content: Buffer.from(`https://${privateHost}/wiki/internal`, 'utf16le'),
      expected: /private knowledge link/,
    },
    {
      path: 'config/utf16-provider.bin',
      content: utf16BigEndian(`api_key = "${'sk-live-' + 'U'.repeat(32)}"`),
      expected: /high-confidence secret/,
    },
    {
      path: 'docs/.cache/live.env',
      content: `API_KEY=${'sk-live-' + 'C'.repeat(32)}\n`,
      expected: /forbidden path/,
    },
    {
      path: 'src/.venv/live.env',
      content: `API_KEY=${'sk-live-' + 'V'.repeat(32)}\n`,
      expected: /forbidden path/,
    },
    {
      path: 'pkg/__pycache__/live.env',
      content: `API_KEY=${'sk-live-' + 'P'.repeat(32)}\n`,
      expected: /forbidden path/,
    },
    {
      path: 'docs/guide.md',
      content: `https://${privateHost}/wiki/internal\n`,
      expected: /private knowledge link/,
    },
    { path: 'runtime/data/export.json', content: '{}\n', expected: /forbidden path/ },
    { path: 'data/public/contact.txt', content: 'telephone: 010 1234 5678\n', expected: /sensitive public data/ },
    { path: 'data/public/nul.txt', content: Buffer.from('safe\0hidden'), expected: /NUL byte/ },
    {
      path: 'assets/history.bin',
      content: Buffer.from(`https://github.com/${owner}/${repository}`, 'utf16le'),
      expected: /legacy repository reference/,
    },
  ];
  const parents = [];
  t.after(() => parents.forEach((parent) => rmSync(parent, { recursive: true, force: true })));

  for (const fixture of cases) {
    const { parent, root } = createArchive({ 'README.md': '# Safe public source archive\n' });
    parents.push(parent);
    writeUntracked(root, fixture.path, fixture.content);

    const result = runChecker(root);
    const output = result.stdout + result.stderr;
    assert.equal(result.status, 1, `${fixture.path}\n${output}`);
    assert.match(output, new RegExp(fixture.path.replaceAll('.', '\\.')));
    assert.match(output, fixture.expected);
  }
});

test('archive mode rejects escaping symlinks and accepts the canonical homepage symlink', (t) => {
  const unsafe = createArchive({ 'README.md': '# Safe public source archive\n' });
  const unsafeLink = join(unsafe.root, 'public', 'outside');
  mkdirSync(dirname(unsafeLink), { recursive: true });
  symlinkSync('/etc/passwd', unsafeLink);

  const repository = createRepo({
    'runtime/homepages/public/releases/release-1/index.html': '<h1>Published</h1>\n',
    'runtime/homepages/releases/release-1/manifest.json': '{}\n',
  });
  const active = join(repository, 'runtime/homepages/public/active');
  symlinkSync('releases/release-1', active);
  execFileSync('git', ['add', 'runtime/homepages/public/active'], { cwd: repository });
  const safe = createArchiveFromRepo(repository);
  t.after(() => {
    rmSync(unsafe.parent, { recursive: true, force: true });
    rmSync(safe.parent, { recursive: true, force: true });
  });

  const unsafeResult = runChecker(unsafe.root);
  assert.equal(unsafeResult.status, 1, unsafeResult.stdout + unsafeResult.stderr);
  assert.match(unsafeResult.stdout + unsafeResult.stderr, /unsafe symlink: public\/outside/);

  const safeResult = runChecker(safe.root);
  assert.equal(safeResult.status, 0, safeResult.stdout + safeResult.stderr);
  assert.match(safeResult.stdout, /archive mode/);

  rmSync(join(safe.root, 'runtime/homepages/public/releases/release-1/index.html'));
  const missingAssetResult = runChecker(safe.root);
  assert.equal(missingAssetResult.status, 1, missingAssetResult.stdout + missingAssetResult.stderr);
  assert.match(missingAssetResult.stdout + missingAssetResult.stderr, /invalid homepage active symlink/);
});

test('archive mode fails closed when Git metadata is injected or invalid', (t) => {
  const { parent, root } = createArchive({ 'README.md': '# Safe public source archive\n' });
  mkdirSync(join(root, '.git'));
  t.after(() => rmSync(parent, { recursive: true, force: true }));

  const result = runChecker(root);

  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.match(result.stdout + result.stderr, /Git metadata exists/);
});

test('archive dependency exclusions require explicit installed mode', (t) => {
  const { parent, root } = createArchive({ 'README.md': '# Safe public source archive\n' });
  writeUntracked(
    root,
    'apps/web/node_modules/injected/live.env',
    `API_KEY=${'sk-live-' + 'D'.repeat(32)}\n`,
  );
  t.after(() => rmSync(parent, { recursive: true, force: true }));

  const pristineResult = runChecker(root);
  assert.equal(pristineResult.status, 1, pristineResult.stdout + pristineResult.stderr);
  assert.match(pristineResult.stdout + pristineResult.stderr, /apps\/web\/node_modules/);

  const installedResult = runChecker(root, '--allow-installed-dependencies');
  assert.equal(installedResult.status, 0, installedResult.stdout + installedResult.stderr);
  assert.match(installedResult.stdout, /archive mode/);
});

test('archive mode rejects validator and package-manager cache paths', (t) => {
  const cacheNames = [
    '.mypy_cache', '.nox', '.pnpm-store', '.pytest_cache', '.ruff_cache', '.tox',
  ];
  const parents = [];
  t.after(() => parents.forEach((parent) => rmSync(parent, { recursive: true, force: true })));

  for (const cacheName of cacheNames) {
    const { parent, root } = createArchive({ 'README.md': '# Safe public source archive\n' });
    parents.push(parent);
    writeUntracked(root, `packages/example/${cacheName}/state.txt`, 'generated state\n');

    const result = runChecker(root);
    assert.equal(result.status, 1, `${cacheName}\n${result.stdout}${result.stderr}`);
    assert.match(result.stdout + result.stderr, /forbidden path/);
  }
});

test('rejects tracked environment files while allowing the example template', (t) => {
  const root = createRepo({
    '.env.example': 'API_KEY=replace-me\n',
    '.env.local': 'API_KEY=replace-me\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);

  assert.equal(result.status, 1);
  assert.match(result.stdout + result.stderr, /\.env\.local/);
  assert.doesNotMatch(result.stdout + result.stderr, /forbidden path: \.env\.example/);
});

test('rejects private directories, runtime data, caches, and private screenshots', (t) => {
  const root = createRepo({
    'docs/tutorial-wiki/chapter.md': '# Internal chapter\n',
    'data/private/export.json': '{}\n',
    'runtime/cache/provider-response.json': '{}\n',
    'exports/companies.csv': 'name\nExample\n',
    'captures/admin-session-screenshot.png': 'image fixture\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  for (const path of [
    'docs/tutorial-wiki/chapter.md',
    'data/private/export.json',
    'runtime/cache/provider-response.json',
    'exports/companies.csv',
    'captures/admin-session-screenshot.png',
  ]) {
    assert.match(output, new RegExp(path.replaceAll('.', '\\.')));
  }
});

test('private path tokens use segment boundaries without matching ordinary words', (t) => {
  const root = createRepo({
    'data/private-export/records.json': '{}\n',
    'content/internal-private/notes.md': 'internal\n',
    'private.json': '{}\n',
    'src/privateer.ts': 'export const role = "privateer";\n',
    'docs/deprivate-guide.md': '# Guide\n',
    'content/privately-owned.md': '# Public article\n',
    'data/private data/users.json': '{}\n',
    'content/internal private/notes.md': 'internal\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  assert.equal(result.status, 1);
  for (const path of [
    'data/private-export/records.json',
    'content/internal-private/notes.md',
    'private.json',
    'data/private data/users.json',
    'content/internal private/notes.md',
  ]) {
    assert.match(output, new RegExp(path.replaceAll('.', '\\.')));
  }
  for (const path of [
    'src/privateer.ts',
    'docs/deprivate-guide.md',
    'content/privately-owned.md',
  ]) {
    assert.doesNotMatch(output, new RegExp(path.replaceAll('.', '\\.')));
  }
});

test('rejects generic private, wiki, and runtime data paths while allowing public data assets', (t) => {
  const root = createRepo({
    'private/notes.md': 'internal\n',
    'packages/api/private/config.txt': 'internal\n',
    'docs/wiki/runbook.md': 'internal\n',
    'knowledge/internal-wiki/notes.md': 'internal\n',
    'runtime/data/snapshot.json': '{}\n',
    'runtime/homepages/releases/public/source/index.html': '<h1>Public</h1>\n',
    'public/data/companies.csv': 'name\nExample\n',
    'data/public/example.jsonl': '{"name":"Example"}\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  assert.equal(result.status, 1);
  for (const path of [
    'private/notes.md',
    'packages/api/private/config.txt',
    'docs/wiki/runbook.md',
    'knowledge/internal-wiki/notes.md',
    'runtime/data/snapshot.json',
  ]) {
    assert.match(output, new RegExp(path.replaceAll('.', '\\.')));
  }
  for (const path of [
    'runtime/homepages/releases/public/source/index.html',
    'public/data/companies.csv',
    'data/public/example.jsonl',
  ]) {
    assert.doesNotMatch(output, new RegExp(path.replaceAll('.', '\\.')));
  }
});

test('public data allowlists never permit databases, dumps, backups, or spreadsheets', (t) => {
  const root = createRepo({
    'public/data/customers.sqlite': 'database fixture\n',
    'runtime/homepages/releases/public/backup.sql': 'database dump\n',
    'data/public/accounts.xlsx': 'spreadsheet fixture\n',
    'public/assets/signing.pfx': 'key container fixture\n',
    'assets/public/application.jks': 'key container fixture\n',
    'data/public/server.key': 'key fixture\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  assert.equal(result.status, 1);
  for (const path of [
    'public/data/customers.sqlite',
    'runtime/homepages/releases/public/backup.sql',
    'data/public/accounts.xlsx',
    'public/assets/signing.pfx',
    'assets/public/application.jks',
    'data/public/server.key',
  ]) {
    assert.match(output, new RegExp(path.replaceAll('.', '\\.')));
  }
});

test('runtime paths default to deny with a narrow homepage publishing allowlist', (t) => {
  const root = createRepo({
    'runtime/homepages/public/releases/release-1/index.html': '<h1>Published</h1>\n',
    'runtime/homepages/releases/release-1/manifest.json': '{"entry_path":"index.html"}\n',
    'runtime/homepages/releases/release-1/source/index.html': '<h1>Source</h1>\n',
    'runtime/sessions/admin.json': '{}\n',
    'runtime/exports/companies.json': '{}\n',
    'runtime/users.json': '{}\n',
    'runtime/homepages/releases/release-1/archive.zip': 'archive fixture\n',
    'runtime/homepages/public/releases/release-1/archive.zip': 'archive fixture\n',
    'runtime/homepages/public/releases/release-1/signing.p12': 'binary fixture\n',
    'runtime/other/state.json': '{}\n',
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  assert.equal(result.status, 1);
  for (const path of [
    'runtime/sessions/admin.json',
    'runtime/exports/companies.json',
    'runtime/users.json',
    'runtime/homepages/releases/release-1/archive.zip',
    'runtime/homepages/public/releases/release-1/archive.zip',
    'runtime/homepages/public/releases/release-1/signing.p12',
    'runtime/other/state.json',
  ]) {
    assert.match(output, new RegExp(path.replaceAll('.', '\\.')));
  }
  for (const path of [
    'runtime/homepages/public/releases/release-1/index.html',
    'runtime/homepages/releases/release-1/manifest.json',
    'runtime/homepages/releases/release-1/source/index.html',
  ]) {
    assert.doesNotMatch(output, new RegExp(path.replaceAll('.', '\\.')));
  }
});

test('rejects noncanonical runtime path casing before allowlist checks', (t) => {
  const uppercaseRoot = createRepo({ 'README.md': '# Fixture\n' });
  const uppercaseAsset = join(uppercaseRoot, 'Runtime/homepages/public/releases/r1/index.html');
  mkdirSync(dirname(uppercaseAsset), { recursive: true });
  symlinkSync('/etc/passwd', uppercaseAsset);
  execFileSync('git', ['add', 'Runtime'], { cwd: uppercaseRoot });
  const mixedRoot = createRepo({
    'runtime/Homepages/public/releases/r2/index.html': '<h1>Mixed case</h1>\n',
  });
  t.after(() => {
    rmSync(uppercaseRoot, { recursive: true, force: true });
    rmSync(mixedRoot, { recursive: true, force: true });
  });

  const uppercaseResult = runChecker(uppercaseRoot);
  const mixedResult = runChecker(mixedRoot);

  assert.equal(uppercaseResult.status, 1, uppercaseResult.stdout + uppercaseResult.stderr);
  assert.match(uppercaseResult.stdout + uppercaseResult.stderr, /Runtime\/homepages\/public/);
  assert.equal(mixedResult.status, 1, mixedResult.stdout + mixedResult.stderr);
  assert.match(mixedResult.stdout + mixedResult.stderr, /runtime\/Homepages\/public/);
});

test('active homepage must be a safe tracked release symlink', (t) => {
  const roots = [];
  t.after(() => roots.forEach((root) => rmSync(root, { recursive: true, force: true })));

  const regularFileRoot = createRepo({
    'runtime/homepages/public/active': 'binary\0fixture',
  });
  roots.push(regularFileRoot);

  const invalidTargets = ['/etc', '../sessions', 'releases/missing-release'];
  const invalidSymlinkRoots = invalidTargets.map((target) => {
    const root = createRepo({ 'README.md': '# Fixture\n' });
    const activePath = join(root, 'runtime/homepages/public/active');
    mkdirSync(dirname(activePath), { recursive: true });
    symlinkSync(target, activePath);
    execFileSync('git', ['add', 'runtime/homepages/public/active'], { cwd: root });
    roots.push(root);
    return root;
  });

  const symlinkedEntryRoot = createRepo({
    'runtime/homepages/releases/release-linked/manifest.json': '{}\n',
  });
  let linkedPath = join(
    symlinkedEntryRoot,
    'runtime/homepages/public/releases/release-linked/index.html',
  );
  mkdirSync(dirname(linkedPath), { recursive: true });
  symlinkSync('/etc/passwd', linkedPath);
  let linkedActivePath = join(symlinkedEntryRoot, 'runtime/homepages/public/active');
  symlinkSync('releases/release-linked', linkedActivePath);
  execFileSync('git', ['add', 'runtime'], { cwd: symlinkedEntryRoot });
  roots.push(symlinkedEntryRoot);

  const symlinkedManifestRoot = createRepo({
    'runtime/homepages/public/releases/release-manifest/index.html': '<h1>Published</h1>\n',
  });
  linkedPath = join(
    symlinkedManifestRoot,
    'runtime/homepages/releases/release-manifest/manifest.json',
  );
  mkdirSync(dirname(linkedPath), { recursive: true });
  symlinkSync('/etc/passwd', linkedPath);
  linkedActivePath = join(symlinkedManifestRoot, 'runtime/homepages/public/active');
  mkdirSync(dirname(linkedActivePath), { recursive: true });
  symlinkSync('releases/release-manifest', linkedActivePath);
  execFileSync('git', ['add', 'runtime'], { cwd: symlinkedManifestRoot });
  roots.push(symlinkedManifestRoot);

  const symlinkedAssetRoot = createRepo({
    'runtime/homepages/public/releases/release-asset/index.html': '<h1>Published</h1>\n',
    'runtime/homepages/releases/release-asset/manifest.json': '{}\n',
  });
  linkedPath = join(
    symlinkedAssetRoot,
    'runtime/homepages/public/releases/release-asset/styles.css',
  );
  symlinkSync('/etc/passwd', linkedPath);
  linkedActivePath = join(symlinkedAssetRoot, 'runtime/homepages/public/active');
  symlinkSync('releases/release-asset', linkedActivePath);
  execFileSync('git', ['add', 'runtime'], { cwd: symlinkedAssetRoot });
  roots.push(symlinkedAssetRoot);

  for (const root of [
    regularFileRoot,
    ...invalidSymlinkRoots,
    symlinkedEntryRoot,
    symlinkedManifestRoot,
    symlinkedAssetRoot,
  ]) {
    const result = runChecker(root);
    assert.equal(result.status, 1, result.stdout + result.stderr);
    assert.match(result.stdout + result.stderr, /runtime\/homepages\//);
  }

  const validRoot = createRepo({
    'runtime/homepages/public/releases/release-1/index.html': '<h1>Published</h1>\n',
    'runtime/homepages/releases/release-1/manifest.json': '{}\n',
  });
  roots.push(validRoot);
  const validActivePath = join(validRoot, 'runtime/homepages/public/active');
  mkdirSync(dirname(validActivePath), { recursive: true });
  symlinkSync('releases/release-1', validActivePath);
  execFileSync('git', ['add', 'runtime/homepages/public/active'], { cwd: validRoot });

  const validResult = runChecker(validRoot);
  assert.equal(validResult.status, 0, validResult.stdout + validResult.stderr);

  rmSync(validActivePath);
  symlinkSync('../sessions', validActivePath);
  const brokenWorkingResult = runChecker(validRoot);
  assert.equal(brokenWorkingResult.status, 1, brokenWorkingResult.stdout + brokenWorkingResult.stderr);
  assert.match(brokenWorkingResult.stdout + brokenWorkingResult.stderr, /invalid homepage active symlink/);
});

test('rejects a staged homepage when the working active symlink is missing', (t) => {
  const root = createRepo({
    'runtime/homepages/public/releases/release-active/index.html': '<h1>Published</h1>\n',
    'runtime/homepages/releases/release-active/manifest.json': '{}\n',
  });
  const activePath = join(root, 'runtime/homepages/public/active');
  symlinkSync('releases/release-active', activePath);
  execFileSync('git', ['add', 'runtime/homepages/public/active'], { cwd: root });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const validResult = runChecker(root);
  assert.equal(validResult.status, 0, validResult.stdout + validResult.stderr);

  rmSync(activePath);
  const missingResult = runChecker(root);
  assert.equal(missingResult.status, 1, missingResult.stdout + missingResult.stderr);
  assert.match(missingResult.stdout + missingResult.stderr, /runtime\/homepages\/public\/active/);
});

test('rejects a staged homepage when the working public release index is missing', (t) => {
  const releaseIndex = 'runtime/homepages/public/releases/release-index/index.html';
  const root = createRepo({
    [releaseIndex]: '<h1>Published</h1>\n',
    'runtime/homepages/releases/release-index/manifest.json': '{}\n',
  });
  const activePath = join(root, 'runtime/homepages/public/active');
  symlinkSync('releases/release-index', activePath);
  execFileSync('git', ['add', 'runtime/homepages/public/active'], { cwd: root });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const validResult = runChecker(root);
  assert.equal(validResult.status, 0, validResult.stdout + validResult.stderr);

  rmSync(join(root, releaseIndex));
  const missingResult = runChecker(root);
  assert.equal(missingResult.status, 1, missingResult.stdout + missingResult.stderr);
  assert.match(missingResult.stdout + missingResult.stderr, new RegExp(releaseIndex.replaceAll('.', '\\.')));
});

test('rejects high-confidence secrets, seed admin passwords, and private knowledge links', (t) => {
  const privateHost = ['example-team', 'feishu', 'cn'].join('.');
  const githubKnowledgePath = ['https://github.com/example/project', 'wiki'].join('/');
  const root = createRepo({
    'src/provider.ts': `const apiKey = '${'sk-latest-' + 'A'.repeat(32)}';\n`,
    'backend/app/scripts/seed.py': `ADMIN_SEED_PASSWORD = "${'A9!' + 'x'.repeat(20)}"\n`,
    'README.md': `https://${privateHost}/wiki/example\n${githubKnowledgePath}\n`,
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  assert.equal(result.status, 1);
  assert.match(output, /high-confidence secret: src\/provider\.ts/);
  assert.match(output, /hard-coded seed admin password: backend\/app\/scripts\/seed\.py/);
  assert.match(output, /private knowledge link: README\.md/);
});

test('public gate rejects normalized private contact data', (t) => {
  const root = createRepo({
    'data/public/mobile.json': JSON.stringify({bio: '联系号码 138 0013 8000'}),
    'data/public/landline.json': JSON.stringify({bio: 'telephone: 010 1234 5678'}),
    'runtime/homepages/releases/entity/source/index.html': 'mailto&#58;person&commat;example&period;com',
    'runtime/homepages/releases/entity-no-semicolon/source/index.html': 'person&#64example&#46com',
  });
  t.after(() => rmSync(root, {recursive: true, force: true}));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;
  assert.equal(result.status, 1, output);
  assert.match(output, /sensitive public data: data\/public\/mobile\.json/);
  assert.match(output, /sensitive public data: data\/public\/landline\.json/);
  assert.match(output, /sensitive public data: runtime\/homepages\/releases\/entity\/source\/index\.html/);
  assert.match(output, /sensitive public data: runtime\/homepages\/releases\/entity-no-semicolon\/source\/index\.html/);
});

test('public gate rejects address-shaped text and bare phones while allowing DOI links', (t) => {
  const root = createRepo({
    'data/public/address.json': JSON.stringify({bio: '联系地址位于广东省深圳市南山区科苑路15号'}),
    'data/public/hong-kong-address.json': JSON.stringify({bio: '地址：香港九龙尖沙咀弥敦道100号'}),
    'data/public/structured-address.json': JSON.stringify({住址: '北京市朝阳区建国路88号'}),
    'data/public/chinese-number-address.txt': '住址为北京市朝阳区建国路八十八号\n',
    'data/public/phone.txt': '021-61234567\n',
    'data/public/url-phone.txt': 'https://example.com/contact/13800138000\n',
    'data/public/paper.json': JSON.stringify({
      link: 'https://doi.org/10.1234/5678',
      citation: 'doi:10.1234/5678',
      bare: '10.1234/5678',
    }),
    'data/public/address-semantics.txt': '网络地址是市区道路设计规范；项目地址是北京市交通路网数据集。\n',
  });
  t.after(() => rmSync(root, {recursive: true, force: true}));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;
  assert.equal(result.status, 1, output);
  assert.match(output, /sensitive public data: data\/public\/address\.json/);
  assert.match(output, /sensitive public data: data\/public\/hong-kong-address\.json/);
  assert.match(output, /sensitive public data: data\/public\/structured-address\.json/);
  assert.match(output, /sensitive public data: data\/public\/chinese-number-address\.txt/);
  assert.match(output, /sensitive public data: data\/public\/phone\.txt/);
  assert.match(output, /sensitive public data: data\/public\/url-phone\.txt/);
  assert.doesNotMatch(output, /data\/public\/paper\.json/);
  assert.doesNotMatch(output, /data\/public\/address-semantics\.txt/);
});

test('legacy owner cannot bypass the gate through history or runtime release paths', (t) => {
  const owner = ['AI', 'haoke'].join('');
  const repository = 'GEORank';
  const root = createRepo({
    'docs/history/new.md': `https://github.com/${owner}/${repository}.git\n`,
    'runtime/homepages/releases/new/source/index.html': `git@github.com:${owner}/${repository}.git\n`,
    'runtime/homepages/releases/entity/source/index.html': `https://github.com/${owner}&#47;${repository}\n`,
    'runtime/homepages/releases/entity-no-semicolon/source/index.html': `https://github.com/${owner}&#x2f${repository}\n`,
    'assets/history.bin': Buffer.concat([
      Buffer.from([0]),
      Buffer.from(`ssh://git@github.com/${owner}/${repository}.git`),
    ]),
  });
  t.after(() => rmSync(root, {recursive: true, force: true}));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;
  assert.equal(result.status, 1, output);
  assert.match(output, /legacy repository reference: docs\/history\/new\.md/);
  assert.match(output, /legacy repository reference: runtime\/homepages\/releases\/new\/source\/index\.html/);
  assert.match(output, /legacy repository reference: runtime\/homepages\/releases\/entity\/source\/index\.html/);
  assert.match(output, /legacy repository reference: runtime\/homepages\/releases\/entity-no-semicolon\/source\/index\.html/);
  assert.match(output, /legacy repository reference: assets\/history\.bin/);
});

test('public text cannot use NUL bytes to bypass staged or working scans', (t) => {
  const stagedRoot = createRepo({
    'data/public/staged.txt': Buffer.from('safe\0telephone: 010 1234 5678'),
    'data/public/opaque.custom': Buffer.from('safe\0wxid_example_2026'),
    'assets/public/logo.png': Buffer.from([0, 1, 2, 3]),
  });
  t.after(() => rmSync(stagedRoot, {recursive: true, force: true}));
  let result = runChecker(stagedRoot);
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.match(result.stdout + result.stderr, /NUL byte in public text: data\/public\/staged\.txt/);
  assert.match(result.stdout + result.stderr, /NUL byte in public text: data\/public\/opaque\.custom/);
  assert.doesNotMatch(result.stdout + result.stderr, /assets\/public\/logo\.png/);

  writeFileSync(join(stagedRoot, 'data/public/staged.txt'), 'sanitized working copy\n');
  result = runChecker(stagedRoot);
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.match(result.stdout + result.stderr, /NUL byte in public text: data\/public\/staged\.txt/);

  const workingRoot = createRepo({'data/public/working.txt': 'clean staged copy\n'});
  t.after(() => rmSync(workingRoot, {recursive: true, force: true}));
  writeFileSync(join(workingRoot, 'data/public/working.txt'), Buffer.from('safe\0wxid_example_2026'));
  result = runChecker(workingRoot);
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.match(result.stdout + result.stderr, /NUL byte in public text: data\/public\/working\.txt/);
});

test('rejects standard private-key PEM headers regardless of file extension', (t) => {
  const root = createRepo({
    'fixtures/encrypted.txt': `${privateKeyHeader('ENCRYPTED')}\n${'A'.repeat(32)}\n`,
    'fixtures/dsa.txt': `${privateKeyHeader('DSA')}\n${'B'.repeat(32)}\n`,
    'fixtures/ec.txt': `${privateKeyHeader('EC')}\n${'C'.repeat(32)}\n`,
    'fixtures/rsa.txt': `${privateKeyHeader('RSA')}\n${'D'.repeat(32)}\n`,
    'fixtures/openssh.txt': `${privateKeyHeader('OPENSSH')}\n${'E'.repeat(32)}\n`,
    'fixtures/pkcs8.txt': `${privateKeyHeader()}\n${'F'.repeat(32)}\n`,
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  assert.equal(result.status, 1);
  for (const path of [
    'fixtures/encrypted.txt',
    'fixtures/dsa.txt',
    'fixtures/ec.txt',
    'fixtures/rsa.txt',
    'fixtures/openssh.txt',
    'fixtures/pkcs8.txt',
  ]) {
    assert.match(output, new RegExp(`high-confidence secret: ${path.replaceAll('.', '\\.')}`));
  }
});

test('rejects administrator JWT and session tokens in tracked configuration', (t) => {
  const jwt = `${Buffer.from('{"alg":"HS256"}').toString('base64url')}.${Buffer.from('{"role":"admin","sub":"1"}').toString('base64url')}.${'S'.repeat(43)}`;
  const root = createRepo({
    'backend/config/admin.env': `ADMIN_SESSION_TOKEN=${'aB9_' + 'x'.repeat(44)}\n`,
    'src/admin-config.ts': `export const adminJwt = \`${jwt}\`;\n`,
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  assert.equal(result.status, 1);
  assert.match(output, /high-confidence secret: backend\/config\/admin\.env/);
  assert.match(output, /high-confidence secret: src\/admin-config\.ts/);
});

test('rejects unquoted env and YAML credential assignments', (t) => {
  const root = createRepo({
    'config/provider.yaml': `api_key: LiveKey_A9${'x'.repeat(24)}\nsecret: LiveSecret_8${'y'.repeat(20)}\n`,
    'config/runtime.env': `PASSWORD=ProdPass_7!${'z'.repeat(20)}\nTOKEN=LiveToken_6_${'q'.repeat(20)}\n`,
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  assert.equal(result.status, 1);
  assert.match(output, /high-confidence secret: config\/provider\.yaml/);
  assert.match(output, /high-confidence secret: config\/runtime\.env/);
});

test('rejects session cookies and encryption material across assignment styles', (t) => {
  const root = createRepo({
    'src/session-config.ts': [
      `const sessionId = "${'SessId_7!' + 's'.repeat(24)}";`,
      `const adminSessionCookie = \`${'AdminCookie_8_' + 'c'.repeat(24)}\`;`,
      '',
    ].join('\n'),
    'src/encryption-config.js': [
      `const settingsEncryptionKey = '${'SettingsKey_9!' + 'k'.repeat(24)}';`,
      `const privateKey = \`${'PrivateKey_6_' + 'p'.repeat(24)}\`;`,
      '',
    ].join('\n'),
    'config/security.env': `SESSION_COOKIE=${'Cookie_5!' + 'e'.repeat(24)}\n`,
    'config/crypto.yaml': [
      `encryption_key: ${'Encrypt_4!' + 'y'.repeat(24)}`,
      `private_key: ${'Private_3!' + 'z'.repeat(24)}`,
      '',
    ].join('\n'),
    'config/session.json': JSON.stringify({
      sessionCookie: `${'JsonCookie_2!' + 'j'.repeat(24)}`,
    }),
    'config/quoted-private.yaml': `"private_key": ${'JsonPrivate_1!' + 'v'.repeat(24)}\n`,
    'src/secret-key.ts': `const SECRET_KEY = "${'SecretKey_4!' + 'a'.repeat(24)}";\n`,
    'src/master-key.ts': `const masterKey = \`${'MasterKey_5_' + 'b'.repeat(24)}\`;\n`,
    'config/fernet.env': `FERNET_KEY=${'FernetKey_6!' + 'c'.repeat(24)}\n`,
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  assert.equal(result.status, 1);
  for (const path of [
    'src/session-config.ts',
    'src/encryption-config.js',
    'config/security.env',
    'config/crypto.yaml',
    'config/session.json',
    'config/quoted-private.yaml',
    'src/secret-key.ts',
    'src/master-key.ts',
    'config/fernet.env',
  ]) {
    assert.match(output, new RegExp(`high-confidence secret: ${path.replaceAll('.', '\\.')}`));
  }
});

test('rejects template-literal administrator seed passwords', (t) => {
  const root = createRepo({
    'backend/scripts/admin-seed.ts': `const ADMIN_SEED_PASSWORD = \`ProdSeed_9!${'m'.repeat(20)}\`;\n`,
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  assert.equal(result.status, 1);
  assert.match(output, /hard-coded seed admin password: backend\/scripts\/admin-seed\.ts/);
});

test('allows explicit placeholders and ignores forbidden untracked files', (t) => {
  const root = createRepo({
    '.env.example': [
      'API_KEY=replace-me',
      'ADMIN_PASSWORD=test-password',
      'DATABASE_PASSWORD=${DATABASE_PASSWORD:?replace-me-database-password}',
      'SESSION_COOKIE=your-session-cookie-here',
      'SETTINGS_ENCRYPTION_KEY=replace-me-settings-encryption-key',
      'PRIVATE_KEY=test-private-key-fixture',
      '',
    ].join('\n'),
    'src/config.ts': [
      'const token = "your-token-here";',
      `const apiKey = "${'sk-test-' + 'A'.repeat(32)}";`,
      'const sessionId = "test-session-id-fixture";',
      'const privateKey = `your-private-key-here`;',
      '',
    ].join('\n'),
  });
  writeUntracked(root, '.env.local', `API_KEY=${'sk-' + 'Z'.repeat(32)}\n`);
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);

  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('does not treat sentinel words embedded in live credentials as placeholders', (t) => {
  const root = createRepo({
    'config/live.env': `API_KEY=${'sk-live-your-' + 'L'.repeat(32)}\n`,
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);

  assert.equal(result.status, 1);
  assert.match(result.stdout + result.stderr, /high-confidence secret: config\/live\.env/);
});

test('rejects live environment fallbacks while allowing sentinel fallbacks', (t) => {
  const root = createRepo({
    '.env.example': 'SESSION_COOKIE=${SESSION_COOKIE:-test-session-cookie}\n',
    'config/runtime.env': `SETTINGS_ENCRYPTION_KEY=\${SETTINGS_ENCRYPTION_KEY:-${'LiveKey_A9' + 'L'.repeat(24)}}\n`,
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);
  const output = result.stdout + result.stderr;

  assert.equal(result.status, 1);
  assert.match(output, /high-confidence secret: config\/runtime\.env/);
  assert.doesNotMatch(output, /high-confidence secret: \.env\.example/);
});

test('handles tracked symlinks without following their directory targets', (t) => {
  const root = createRepo({ 'dist/js/app.js': 'console.log("public");\n' });
  mkdirSync(join(root, 'public'), { recursive: true });
  symlinkSync('../dist/js', join(root, 'public/js'));
  execFileSync('git', ['add', 'public/js'], { cwd: root });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);

  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('rejects an unsafe staged symlink after the working link is sanitized', (t) => {
  const root = createRepo({ 'dist/js/app.js': 'console.log("public");\n' });
  const link = join(root, 'public', 'js');
  mkdirSync(dirname(link), { recursive: true });
  symlinkSync('/etc/passwd', link);
  execFileSync('git', ['add', 'public/js'], { cwd: root });
  rmSync(link);
  symlinkSync('../dist/js', link);
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);

  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.match(result.stdout + result.stderr, /unsafe symlink: public\/js/);
});

test('scans the staged snapshot when the working copy is sanitized later', (t) => {
  const root = createRepo({
    'src/provider.ts': `const apiKey = "${'sk-' + 'Q'.repeat(32)}";\n`,
  });
  writeUntracked(root, 'src/provider.ts', 'const apiKey = "replace-me";\n');
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);

  assert.equal(result.status, 1);
  assert.match(result.stdout + result.stderr, /high-confidence secret: src\/provider\.ts/);
});

test('checks every credential-shaped value after an allowed test value', (t) => {
  const root = createRepo({
    '.env.example': [
      `PRIMARY_KEY=${'sk-test-' + 'T'.repeat(32)}`,
      `SECONDARY_KEY=${'sk-' + 'R'.repeat(32)}`,
      '',
    ].join('\n'),
  });
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const result = runChecker(root);

  assert.equal(result.status, 1);
  assert.match(result.stdout + result.stderr, /high-confidence secret: \.env\.example/);
});
