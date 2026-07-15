import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync, readdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
import test from 'node:test';
import {parse as parseYaml} from 'yaml';

import {
  collectReleaseContractErrors,
  readBackendWorkflow,
  readCliWorkflow,
  readContainerContract,
  readFrontendWorkflow,
} from './release-contract.mjs';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');

test('product and independently versioned components follow the release policy', async () => {
  const errors = await collectReleaseContractErrors(repoRoot);
  assert.deepEqual(
    errors.filter((error) => error.startsWith('version:')),
    [],
  );

  const rootPackage = JSON.parse(readFileSync(resolve(repoRoot, 'package.json'), 'utf8'));
  assert.equal(rootPackage.name, 'georank');
  assert.equal(rootPackage.version, '1.3.0');
  assert.deepEqual(rootPackage.pnpm, {
    onlyBuiltDependencies: ['@parcel/watcher', '@swc/core', 'sharp'],
  });
  assert.equal(
    rootPackage.scripts['release:check'],
    'pnpm release:contract && pnpm sdk:check && pnpm public:check && pnpm i18n:check && pnpm typecheck && pnpm build',
  );
});

test('backend CI exercises migrations, tests, schema drift, and the Python 3.10 crawler', async () => {
  const workflow = await readBackendWorkflow(repoRoot);
  const testCommands = workflow.jobs.test.steps
    .map((step) => step.run)
    .filter(Boolean);
  const commands = workflow.jobs['crawler-smoke'].steps
    .map((step) => step.run)
    .filter(Boolean);

  assert.deepEqual(testCommands, [
    'pip install -r requirements.txt',
    'python scripts/export_openapi.py --check ../packages/api-sdk/openapi.json',
    'alembic upgrade head',
    'python -m tests.run',
    'scripts/check-container-migration-bootstrap.sh',
  ]);
  assert.deepEqual(commands, [
    'docker build --file backend/Dockerfile.crawler --tag georank-crawler-ci backend',
    'docker run --rm --entrypoint python georank-crawler-ci scripts/crawler_import_smoke.py',
  ]);
  assert.ok(workflow.on.pull_request.paths.includes('backend/**'));
  assert.ok(workflow.on.pull_request.paths.includes('infra/**'));
  assert.ok(workflow.on.pull_request.paths.includes('docker-compose*.yml'));
  assert.ok(workflow.on.pull_request.paths.includes('packages/api-sdk/openapi.json'));
  assert.ok(workflow.on.push.paths.includes('infra/**'));
  assert.ok(workflow.on.push.paths.includes('docker-compose*.yml'));
  assert.ok(workflow.on.push.paths.includes('packages/api-sdk/openapi.json'));
  assert.equal(workflow.permissions.contents, 'read');
});

test('CLI CI installs the package and exercises its complete test suite', async () => {
  const workflow = await readCliWorkflow(repoRoot);
  const commands = workflow.jobs.cli.steps
    .map((step) => step.run)
    .filter(Boolean);

  assert.deepEqual(commands, [
    'pip install --disable-pip-version-check -e ./cli',
    'python -m unittest discover -s cli/tests -v',
    'georank --version',
  ]);
  assert.ok(workflow.on.pull_request.paths.includes('cli/**'));
  assert.equal(workflow.permissions.contents, 'read');
});

test('Compose and Dockerfiles use immutable multi-architecture image references', async () => {
  const contract = await readContainerContract(repoRoot);

  assert.equal(contract.compose.version, undefined);
  assert.deepEqual(contract.images, {
    traefik: 'traefik:v3.1.7@sha256:74d72c7a1345984f186bddbabcc462b2128d0d8054177dc84afaeac4db1f0f56',
    frontend: 'nginx:1.27.5-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10',
    postgres: 'postgres:16.9-alpine@sha256:7c688148e5e156d0e86df7ba8ae5a05a2386aaec1e2ad8e6d11bdf10504b1fb7',
    redis: 'redis:7.4.5-alpine@sha256:bb186d083732f669da90be8b0f975a37812b15e913465bb14d845db72a4e3e08',
    qdrant: 'qdrant/qdrant:v1.12.1@sha256:d774e7bb65744454984c6021637a0da89271f30df15e48601a9fafc926d26b1f',
    neo4j: 'neo4j:5.24.2-community@sha256:2e7e4eea5bc1eec581a3097c018dfeb3747f3638e67a963c10554825c31c1425',
    minio: 'minio/minio:RELEASE.2025-04-22T22-12-26Z@sha256:a1ea29fa28355559ef137d71fc570e508a214ec84ff8083e39bc5428980b015e',
  });
  assert.equal(
    contract.backendBase,
    'python:3.12.13-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b',
  );
  assert.equal(
    contract.crawlerBase,
    'mcr.microsoft.com/playwright/python:v1.49.1-jammy@sha256:a34c7c0c74cc5c94f39bedbee2cb220b1e0c0408c78610eade5ab1db32c3294f',
  );
});

test('production gateway uses only the file provider and Compose service DNS', () => {
  const compose = parseYaml(readFileSync(resolve(repoRoot, 'docker-compose.yml'), 'utf8'));
  const staticConfig = parseYaml(readFileSync(resolve(repoRoot, 'infra/traefik/traefik.yml'), 'utf8'));
  const routes = parseYaml(readFileSync(resolve(repoRoot, 'infra/traefik/dynamic/routes.yml'), 'utf8'));

  assert.deepEqual(Object.keys(staticConfig.providers), ['file']);
  assert.equal(staticConfig.providers.file.directory, '/etc/traefik/dynamic');
  assert.equal(staticConfig.providers.file.watch, true);

  const traefikVolumes = compose.services.traefik.volumes ?? [];
  assert.equal(
    traefikVolumes.some((volume) => String(volume).includes('docker.sock')),
    false,
    'Traefik must not receive the Docker Engine socket',
  );
  assert.equal(compose.services.frontend.labels, undefined);
  assert.equal(compose.services.api.labels, undefined);
  assert.deepEqual(compose.services.traefik.ports, [
    '${GEORANK_HTTP_PORT:-80}:80',
    '${GEORANK_HTTPS_PORT:-443}:443',
  ]);
  for (const serviceName of [
    'frontend', 'api', 'postgres', 'redis', 'qdrant', 'neo4j', 'minio',
  ]) {
    assert.equal(
      compose.services[serviceName].ports,
      undefined,
      `${serviceName} must remain private to the Compose network`,
    );
  }
  assert.ok(traefikVolumes.includes('./infra/traefik:/etc/traefik:ro'));
  assert.ok(traefikVolumes.includes('traefik_acme:/var/lib/traefik'));
  assert.equal(staticConfig.api?.dashboard, false);
  assert.equal(staticConfig.api?.insecure, false);
  assert.match(
    readFileSync(resolve(repoRoot, 'infra/traefik/traefik.yml'), 'utf8'),
    /storage: \/var\/lib\/traefik\/acme\.json/,
  );

  assert.equal(
    routes.http.services['frontend-svc'].loadBalancer.servers[0].url,
    'http://frontend:80',
  );
  assert.equal(
    routes.http.services['api-svc'].loadBalancer.servers[0].url,
    'http://api:8000',
  );
  assert.equal(
    routes.http.routers.api.rule,
    'Path(`/api`) || PathPrefix(`/api/`)',
  );
  assert.doesNotMatch(
    readFileSync(resolve(repoRoot, 'infra/traefik/dynamic/routes.yml'), 'utf8'),
    /georank-(?:frontend|api)/,
  );

  for (const serviceName of ['traefik', 'frontend', 'api']) {
    assert.ok(compose.services[serviceName].networks.includes('georank-net'));
  }

  const effectiveCompose = parseYaml(execFileSync(
    'docker',
    ['compose', 'config', '--format', 'yaml'],
    {
      cwd: repoRoot,
      encoding: 'utf8',
      env: {
        ...process.env,
        GEORANK_ENV_FILE: '.env.example',
        POSTGRES_PASSWORD: 'test-contract-password',
      },
    },
  ));
  assert.equal(
    effectiveCompose.services.traefik.volumes.some((volume) => volume.source === '/var/run/docker.sock'),
    false,
  );
  const effectiveTraefikConfigMount = effectiveCompose.services.traefik.volumes.find(
    (volume) => volume.target === '/etc/traefik',
  );
  assert.equal(effectiveTraefikConfigMount.read_only, true);
  const effectiveAcmeMount = effectiveCompose.services.traefik.volumes.find(
    (volume) => volume.target === '/var/lib/traefik',
  );
  assert.equal(effectiveAcmeMount.type, 'volume');
  assert.notEqual(effectiveAcmeMount.read_only, true);
  const networkName = effectiveCompose.networks['georank-net'].name;
  for (const serviceName of ['traefik', 'frontend', 'api']) {
    assert.ok(effectiveCompose.services[serviceName].networks['georank-net'] !== undefined);
  }
  assert.match(networkName, /_georank-net$/);
});

test('development override exposes browser surfaces only on loopback', () => {
  const developmentOverride = parseYaml(readFileSync(
    resolve(repoRoot, 'docker-compose.dev.yml'),
    'utf8',
  ));

  assert.deepEqual(Object.keys(developmentOverride.services), ['frontend', 'api']);
  assert.deepEqual(
    developmentOverride.services.frontend.ports,
    ['127.0.0.1:${GEORANK_FRONTEND_PORT:-3009}:80'],
  );
  assert.deepEqual(
    developmentOverride.services.api.ports,
    ['127.0.0.1:${GEORANK_API_PORT:-8000}:8000'],
  );
});

test('static browser clients keep API requests on the frontend origin', () => {
  const javascriptRoot = resolve(repoRoot, 'dist/js');
  const javascriptFiles = readdirSync(javascriptRoot).filter((name) => name.endsWith('.js'));

  for (const name of javascriptFiles) {
    const source = readFileSync(resolve(javascriptRoot, name), 'utf8');
    assert.doesNotMatch(
      source,
      /:8000\b/,
      `${name} must use the frontend's same-origin /api proxy`,
    );
  }
});

test('the active homepage pointer remains deployment-local runtime state', () => {
  const activePath = 'runtime/homepages/public/active';
  const tracked = execFileSync('git', ['ls-files', '--', activePath], {
    cwd: repoRoot,
    encoding: 'utf8',
  }).trim();
  const ignored = execFileSync('git', ['check-ignore', activePath], {
    cwd: repoRoot,
    encoding: 'utf8',
  }).trim();

  assert.equal(tracked, '');
  assert.equal(ignored, activePath);
});

test('container contract exercises the production gateway through the shared network', () => {
  const contract = readFileSync(
    resolve(repoRoot, 'scripts/check-container-migration-bootstrap.sh'),
    'utf8',
  );
  const override = readFileSync(
    resolve(repoRoot, 'docker-compose.migration-contract.yml'),
    'utf8',
  );

  assert.match(contract, /PRODUCTION_GATEWAY:/);
  assert.match(contract, /until curl --fail --silent "\$gateway\/api\/health"/);
  assert.match(contract, /gateway did not become ready/);
  assert.match(contract, /for iteration in \$\(seq 1 40\)/);
  for (const route of ['/', '/api/health', '/api/companies/', '/tutorial', '/experts', '/admin/login']) {
    assert.ok(contract.includes(`"$gateway${route}"`), `missing gateway check for ${route}`);
  }
  assert.ok(contract.includes('"$gateway/apix"'));
  assert.match(contract, /GET \/apix.*frontend@file/);
  assert.match(contract, /failed to retrieve information/);
  assert.match(contract, /status\.\?code\.\?502/);
  assert.match(override, /traefik:\n\s+ports: !override\n\s+- "127\.0\.0\.1:0:80"/);
  assert.match(override, /frontend:\n\s+ports: !override\n\s+- "127\.0\.0\.1:0:80"/);
});

test('frontend CI executes the complete production build contract', async () => {
  const workflow = await readFrontendWorkflow(repoRoot);
  const runCommands = workflow.jobs.frontend.steps
    .map((step) => step.run)
    .filter(Boolean);

  assert.deepEqual(runCommands, [
    'corepack enable',
    'pnpm install --frozen-lockfile',
    'pnpm release:contract',
    'pnpm sdk:check',
    'pnpm public:check',
    'pnpm i18n:check',
    'pnpm --filter @georank/web typecheck',
    'pnpm --filter @georank/admin typecheck',
    'pnpm build',
  ]);
  assert.ok(workflow.on.workflow_dispatch);

  const expectedPaths = [
    'apps/**',
    'packages/**',
    'runtime/homepages/**',
    'README*.md',
    'scripts/check-i18n-hardcoded.mjs',
    'scripts/check-generated-sdk.mjs',
    'scripts/check-public-*.mjs',
    'scripts/public-content-policy*.mjs',
    'scripts/release-contract*.mjs',
    'backend/app/version.py',
    'backend/Dockerfile',
    'backend/Dockerfile.crawler',
    'cli/**',
    'docker-compose*.yml',
    'infra/**',
    'package.json',
    'pnpm-lock.yaml',
    'pnpm-workspace.yaml',
    'turbo.json',
    '.github/workflows/**',
  ];
  assert.deepEqual(workflow.on.pull_request.paths, expectedPaths);
  assert.deepEqual(workflow.on.push.paths, expectedPaths);
});

test('GitHub Actions dependencies are pinned to immutable commits', () => {
  const workflowDirectory = resolve(repoRoot, '.github/workflows');
  const paths = readdirSync(workflowDirectory)
    .filter((path) => /\.ya?ml$/.test(path))
    .map((path) => `.github/workflows/${path}`);

  for (const path of paths) {
    const workflow = readFileSync(resolve(repoRoot, path), 'utf8');
    const actions = [...workflow.matchAll(/uses:\s+([^\s#]+)/g)].map((match) => match[1]);
    for (const action of actions) {
      assert.match(action, /@[0-9a-f]{40}$/, `${path} must pin ${action} to a commit SHA`);
    }
    assert.match(workflow, /^permissions:\s*\n\s+contents:\s+read$/m);
  }
});

test('release engineering policy documents product and component version lifecycles', () => {
  const policy = readFileSync(resolve(repoRoot, 'docs/release-engineering.md'), 'utf8');
  assert.match(policy, /Product release.*1\.3\.0/s);
  assert.match(policy, /API SDK.*0\.1\.0/s);
  assert.match(policy, /CLI.*0\.1\.0/s);
  assert.match(policy, /Python 3\.12.*Python 3\.10/s);
  assert.match(policy, /onlyBuiltDependencies/);
  assert.match(policy, /pnpm release:check/);
});

test('Chinese and English deployment docs state the gateway and TLS boundary', () => {
  const chinese = readFileSync(resolve(repoRoot, 'README.md'), 'utf8');
  const english = readFileSync(resolve(repoRoot, 'README.en.md'), 'utf8');

  for (const document of [chinese, english]) {
    assert.match(document, /file provider/i);
    assert.match(document, /Docker socket/i);
    assert.match(document, /HTTPS/);
    assert.match(document, /TLS/);
    assert.match(document, /GEORANK_HTTP_PORT/);
    assert.match(document, /GEORANK_FRONTEND_PORT/);
    assert.match(document, /docker-compose\.dev\.yml/);
    assert.match(document, /\/var\/lib\/traefik\/acme\.json/);
  }
});
