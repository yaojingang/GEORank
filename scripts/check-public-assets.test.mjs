import assert from 'node:assert/strict';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {existsSync, lstatSync, readFileSync, readlinkSync} from 'node:fs';
import {join, resolve} from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

import {
  findSensitivePublicData,
  hasLegacyRepositoryReference,
  hasLegacyRepositoryReferenceInBuffer,
} from './public-content-policy.mjs';
import {collectPublicFileInventory} from './public-file-inventory.mjs';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const fixturePath = join(root, 'data/public/experts.json');
const schemaPath = join(root, 'data/public/schemas/experts.v1.schema.json');
const stateSchemaPath = join(root, 'data/public/schemas/expert-state-transition.v1.schema.json');
const expectedExperts = new Map([
  ['yao-jingang', '姚金刚'],
  ['qiao-xiangyang', '乔向阳'],
  ['fu-wei', '夫唯'],
  ['guangtou-niuge', '光头牛哥'],
  ['zhang-kai', '张凯'],
]);

function loadFixture() {
  assert.equal(existsSync(fixturePath), true, 'canonical public expert fixture must exist');
  return JSON.parse(readFileSync(fixturePath, 'utf8'));
}

function compileJsonSchema(path) {
  assert.equal(existsSync(path), true, `JSON Schema must exist: ${path}`);
  const schema = JSON.parse(readFileSync(path, 'utf8'));
  const ajv = new Ajv2020({allErrors: true, strictTuples: false});
  addFormats(ajv);
  return ajv.compile(schema);
}

test('canonical expert fixture satisfies the versioned structural schema', () => {
  const validate = compileJsonSchema(schemaPath);
  const fixture = loadFixture();
  assert.equal(validate(fixture), true, JSON.stringify(validate.errors));

  const missingRequiredField = structuredClone(fixture);
  delete missingRequiredField.experts[0].name;
  assert.equal(validate(missingRequiredField), false);

  const unexpectedField = structuredClone(fixture);
  unexpectedField.experts[0].telephone = 'placeholder';
  assert.equal(validate(unexpectedField), false);

  const unsafeAvatar = structuredClone(fixture);
  unsafeAvatar.experts[0].avatar_url = 'javascript:alert(1)';
  assert.equal(validate(unsafeAvatar), false);

  const insecureAvatar = structuredClone(fixture);
  insecureAvatar.experts[0].avatar_url = 'http://example.com/avatar.png';
  assert.equal(validate(insecureAvatar), false);

  const secureAvatar = structuredClone(fixture);
  secureAvatar.experts[0].avatar_url = 'https://example.com/avatar.png';
  assert.equal(validate(secureAvatar), true, JSON.stringify(validate.errors));
});

test('future tombstone projection satisfies versioned fixture and state schemas', () => {
  const validateFixture = compileJsonSchema(schemaPath);
  const validateState = compileJsonSchema(stateSchemaPath);
  const fixture = loadFixture();
  const dryRunFixture = structuredClone(fixture);
  const target = dryRunFixture.experts[0];
  target.status = 'hidden';
  target.featured = false;
  dryRunFixture.migration_chain = [
    {kind: 'seed', snapshot: fixture.migration_snapshot},
    {kind: 'state', snapshot: 'backend/alembic/snapshots/015_unpublish_yao_jingang.json'},
  ];
  const stateSnapshot = {
    schema_version: 1,
    contract: 'expert-state-transition',
    revision: '015_unpublish_yao_jingang',
    down_revision: '016_merge_platform_iterations',
    effective_date: '2026-07-16',
    downgrade_policy: 'preserve_target_state',
    operations: [{
      operation: 'set_publication_state',
      id: target.id,
      slug: target.slug,
      from_state: {is_published: true, is_featured: true},
      to_state: {is_published: false, is_featured: false},
      reason: 'verified rights or privacy request',
    }],
  };

  assert.equal(validateFixture(dryRunFixture), true, JSON.stringify(validateFixture.errors));
  assert.equal(validateState(stateSnapshot), true, JSON.stringify(validateState.errors));
  assert.deepEqual(findSensitivePublicData(dryRunFixture), []);
  assert.equal(fixture.experts.every(({status, featured}) => status === 'published' && featured), true);
  assert.equal(fixture.migration_snapshot, 'backend/alembic/snapshots/012_seed_expert_profiles.json');
  assert.equal(Object.hasOwn(fixture, 'migration_chain'), false);

  const reversedChain = structuredClone(dryRunFixture);
  reversedChain.migration_chain.reverse();
  assert.equal(validateFixture(reversedChain), false);

  const invalidTransition = structuredClone(stateSnapshot);
  delete invalidTransition.operations[0].slug;
  assert.equal(validateState(invalidTransition), false);

  const republishTransition = structuredClone(stateSnapshot);
  republishTransition.operations[0].from_state = {is_published: false, is_featured: false};
  republishTransition.operations[0].to_state = {is_published: true, is_featured: true};
  assert.equal(validateState(republishTransition), false);
});

test('canonical expert content retains the five-profile frozen seed identity', () => {
  const fixture = loadFixture();
  assert.equal(fixture.schema_version, 1);
  assert.equal(fixture.last_verified, '2026-07-15');
  assert.equal(fixture.source, 'user-authorized migration');
  assert.equal(fixture.experts.length, 5);
  const snapshotPath = join(root, 'backend/alembic/snapshots/012_seed_expert_profiles.json');
  assert.equal(existsSync(snapshotPath), true, 'current migration seed snapshot must exist');
  const snapshot = JSON.parse(readFileSync(snapshotPath, 'utf8'));
  assert.equal(snapshot.revision, '012_seed_expert_profiles');
  assert.equal(snapshot.experts.length, 5);
  assert.deepEqual(
    new Map(snapshot.experts.map(({slug, display_name}) => [slug, display_name])),
    expectedExperts,
  );
  assert.equal(snapshot.experts.every(({is_published, is_featured}) => is_published && is_featured), true);

  const ids = new Set();
  const slugs = new Set();
  for (const expert of fixture.experts) {
    assert.match(expert.id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    assert.equal(expectedExperts.get(expert.slug), expert.name);
    assert.equal(expert.source, 'user-authorized migration');
    assert.equal(expert.last_verified, '2026-07-15');
    assert.ok(expert.authorization.length > 20);
    assert.equal(expert.avatar_url, null);
    assert.deepEqual(expert.social_links, []);
    assert.ok(Array.isArray(expert.public_links));
    assert.ok(Array.isArray(expert.expertise) && expert.expertise.every((item) => typeof item === 'string'));
    assert.ok(Array.isArray(expert.keywords) && expert.keywords.every((item) => typeof item === 'string'));
    assert.deepEqual(
      expert.public_links,
      expert.slug === 'yao-jingang'
        ? [{label: 'arXiv paper', url: 'https://arxiv.org/abs/2604.25707'}]
        : [],
    );
    assert.equal(ids.has(expert.id), false, `duplicate expert id: ${expert.id}`);
    assert.equal(slugs.has(expert.slug), false, `duplicate expert slug: ${expert.slug}`);
    ids.add(expert.id);
    slugs.add(expert.slug);
  }
  assert.deepEqual(new Set(slugs), new Set(expectedExperts.keys()));
});

test('canonical expert fixture complies with the reusable public content policy', () => {
  assert.deepEqual(findSensitivePublicData(loadFixture()), []);
});

test('public data license defines rights and update boundaries', () => {
  const licensePath = join(root, 'DATA_LICENSE.md');
  assert.equal(existsSync(licensePath), true, 'DATA_LICENSE.md must exist');
  const content = readFileSync(licensePath, 'utf8');
  assert.match(content, /Apache-2\.0/);
  assert.match(content, /name|姓名/i);
  assert.match(content, /likeness|肖像/i);
  assert.match(content, /trademark|商标/i);
  assert.match(content, /update|更新/i);
  assert.match(content, /remov|移除/i);
  assert.match(content, /GitHub issue/i);
});

test('rights and privacy removal playbook covers every distribution surface', () => {
  const privateReportUrl = 'https://github.com/yaojingang/GEORank/security/advisories/new';
  const dataLicense = readFileSync(join(root, 'DATA_LICENSE.md'), 'utf8');
  const publicDataDocs = readFileSync(join(root, 'docs/public-data.md'), 'utf8');
  const securityPolicy = readFileSync(join(root, 'SECURITY.md'), 'utf8');
  const combined = `${dataLicense}\n${publicDataDocs}`;

  for (const content of [dataLicense, publicDataDocs, securityPolicy]) {
    assert.match(content, new RegExp(privateReportUrl.replaceAll('/', '\\/').replaceAll('.', '\\.')));
    assert.match(content, /Private Vulnerability Reporting/i);
    assert.match(content, /must be enabled|必须启用/i);
  }
  assert.match(combined, /verified rights or privacy request|经核验的权利或隐私请求/i);
  assert.match(combined, /canonical fixture.*(?:hidden|unpublish)|(?:隐藏|停止发布).*canonical fixture/is);
  assert.match(combined, /API.*(?:hidden|stop publishing|unpublish)|(?:隐藏|停止发布).*API/is);
  assert.match(combined, /new.*tombstone.*migration|新增.*tombstone.*迁移/is);
  assert.match(combined, /frozen.*migration.*snapshot|冻结.*迁移.*snapshot/is);
  assert.match(combined, /clean-history rewrite|历史重写/i);
  assert.match(combined, /GitHub sensitive-data purge|GitHub.*敏感数据清除/i);
  assert.match(combined, /release replacement|替换.*release/i);
  assert.match(combined, /fork.*cache.*downstream|fork.*缓存.*下游/is);
  assert.match(combined, /public issue.*slug|公开 issue.*slug/i);
  assert.match(combined, /migration_chain/);
  assert.match(combined, /expert-state-transition\.v1\.schema\.json/);
  assert.match(combined, /expert_migration_contract/);
  assert.match(combined, /state snapshot.*new.*migration|state snapshot.*新增.*迁移/is);
  assert.match(combined, /seed snapshot.*frozen|seed snapshot.*冻结/is);
});

test('public data docs identify canonical expert and homepage sources', () => {
  const docsPath = join(root, 'docs/public-data.md');
  assert.equal(existsSync(docsPath), true, 'docs/public-data.md must exist');
  const content = readFileSync(docsPath, 'utf8');
  assert.match(content, /data\/public\/experts\.json/);
  assert.match(content, /9fe4a087-42bc-423a-bc59-fc020018a6f9/);
  assert.match(content, /runtime\/homepages\/releases\/<release-id>\/source/);
  assert.match(content, /build_zip_homepage_release/);
  assert.match(content, /\/tutorial/);

  for (const readme of ['README.md', 'README.en.md']) {
    const readmeContent = readFileSync(join(root, readme), 'utf8');
    assert.match(readmeContent, /DATA_LICENSE\.md/);
    assert.match(readmeContent, /docs\/public-data\.md/);
  }
});

test('current repository links use the canonical GitHub owner', () => {
  const canonical = 'https://github.com/yaojingang/GEORank';
  for (const publicEntryPoint of ['README.md', 'README.en.md', 'CONTRIBUTING.md']) {
    assert.match(readFileSync(join(root, publicEntryPoint), 'utf8'), new RegExp(canonical));
  }

  const legacyOwner = ['AI', 'haoke'].join('');
  const legacyRepository = 'GEORank';
  for (const legacyVariant of [
    `https://github.com/${legacyOwner}/${legacyRepository}`,
    `https://github.com/${legacyOwner}/${legacyRepository}.git`,
    `git@github.com:${legacyOwner.toUpperCase()}/${legacyRepository.toUpperCase()}.git`,
  ]) {
    assert.equal(hasLegacyRepositoryReference(legacyVariant), true);
  }
  const tracked = collectPublicFileInventory(root, {allowInstalledDependencies: true})
    .entries.map(({path}) => path);
  const offenders = [];
  for (const path of tracked) {
    const absolutePath = join(root, path);
    const payload = lstatSync(absolutePath).isSymbolicLink()
      ? Buffer.from(readlinkSync(absolutePath))
      : readFileSync(absolutePath);
    if (hasLegacyRepositoryReferenceInBuffer(payload)) offenders.push(path);
  }
  assert.deepEqual(offenders, []);
});

test('backend CI watches canonical public data and homepage releases', () => {
  const workflow = readFileSync(join(root, '.github/workflows/backend-ci.yml'), 'utf8');
  for (const pathFilter of ['data/public/**', 'runtime/homepages/**']) {
    const matches = workflow.match(new RegExp(`- "${pathFilter.replaceAll('*', '\\*')}"`, 'g')) || [];
    assert.equal(matches.length, 2, `${pathFilter} must trigger pull request and push checks`);
  }
});

test('public boundary CI installs locked dependencies before running the gate', () => {
  const workflow = readFileSync(join(root, '.github/workflows/public-boundary.yml'), 'utf8');
  const install = workflow.indexOf('pnpm install --frozen-lockfile');
  const gate = workflow.indexOf('pnpm public:check');
  assert.notEqual(install, -1, 'public boundary CI must install the gate dependencies');
  assert.notEqual(gate, -1, 'public boundary CI must run the public gate');
  assert.ok(install < gate, 'dependency installation must precede the public gate');
});

test('public boundary docs describe PII and legacy-owner invariants', () => {
  const docs = readFileSync(join(root, 'docs/public-content-boundary.md'), 'utf8');
  assert.match(docs, /public-content-policy\.mjs/);
  assert.match(docs, /NFKC/);
  assert.match(docs, /phone|telephone|手机|电话/i);
  assert.match(docs, /email|电子邮箱/i);
  assert.match(docs, /WeChat|微信/i);
  assert.match(docs, /legacy.*owner|旧.*owner/i);
  assert.match(docs, /all tracked files|所有 tracked 文件/i);
});
