import {readFile} from 'node:fs/promises';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {parse as parseYaml} from 'yaml';

export const PRODUCT_VERSION = '1.3.0';
export const COMPONENT_VERSIONS = Object.freeze({
  'cli/pyproject.toml': '0.1.0',
  'packages/api-sdk/package.json': '0.1.0',
});

const PRODUCT_PACKAGES = [
  ['package.json', 'georank'],
  ['apps/web/package.json', '@georank/web'],
  ['apps/admin/package.json', '@georank/admin'],
  ['packages/auth/package.json', '@georank/auth'],
  ['packages/i18n/package.json', '@georank/i18n'],
  ['packages/ui/package.json', '@georank/ui'],
];

async function readJson(repoRoot, path) {
  return JSON.parse(await readFile(resolve(repoRoot, path), 'utf8'));
}

export async function readFrontendWorkflow(repoRoot) {
  const content = await readFile(resolve(repoRoot, '.github/workflows/frontend-ci.yml'), 'utf8');
  return parseYaml(content);
}

export async function readBackendWorkflow(repoRoot) {
  const content = await readFile(resolve(repoRoot, '.github/workflows/backend-ci.yml'), 'utf8');
  return parseYaml(content);
}

export async function readCliWorkflow(repoRoot) {
  const content = await readFile(resolve(repoRoot, '.github/workflows/cli-ci.yml'), 'utf8');
  return parseYaml(content);
}

function dockerfileBase(content) {
  return content.match(/^FROM\s+([^\s]+)$/m)?.[1];
}

export async function readContainerContract(repoRoot) {
  const [composeContent, backendDockerfile, crawlerDockerfile] = await Promise.all([
    readFile(resolve(repoRoot, 'docker-compose.yml'), 'utf8'),
    readFile(resolve(repoRoot, 'backend/Dockerfile'), 'utf8'),
    readFile(resolve(repoRoot, 'backend/Dockerfile.crawler'), 'utf8'),
  ]);
  const compose = parseYaml(composeContent);
  const images = Object.fromEntries(
    Object.entries(compose.services)
      .filter(([, service]) => service.image)
      .map(([name, service]) => [name, service.image]),
  );
  return {
    compose,
    images,
    backendBase: dockerfileBase(backendDockerfile),
    crawlerBase: dockerfileBase(crawlerDockerfile),
  };
}

function parseTomlVersion(content) {
  return content.match(/^version\s*=\s*"([^"]+)"/m)?.[1];
}

function parsePythonVersion(content) {
  return content.match(/^PRODUCT_VERSION\s*=\s*"([^"]+)"/m)?.[1];
}

function parsePythonDunderVersion(content) {
  return content.match(/^__version__\s*=\s*"([^"]+)"/m)?.[1];
}

export async function collectReleaseContractErrors(repoRoot) {
  const errors = [];

  for (const [path, expectedName] of PRODUCT_PACKAGES) {
    const manifest = await readJson(repoRoot, path);
    if (manifest.name !== expectedName) {
      errors.push(`version: ${path} name must be ${expectedName}`);
    }
    if (manifest.version !== PRODUCT_VERSION) {
      errors.push(`version: ${path} must use product version ${PRODUCT_VERSION}`);
    }
  }

  const sdkManifest = await readJson(repoRoot, 'packages/api-sdk/package.json');
  if (sdkManifest.version !== COMPONENT_VERSIONS['packages/api-sdk/package.json']) {
    errors.push('version: TypeScript API SDK must use its independent version 0.1.0');
  }

  const cliPyproject = await readFile(resolve(repoRoot, 'cli/pyproject.toml'), 'utf8');
  if (parseTomlVersion(cliPyproject) !== COMPONENT_VERSIONS['cli/pyproject.toml']) {
    errors.push('version: CLI must use its independent version 0.1.0');
  }
  const cliPackage = await readFile(resolve(repoRoot, 'cli/georank_cli/__init__.py'), 'utf8');
  if (parsePythonDunderVersion(cliPackage) !== COMPONENT_VERSIONS['cli/pyproject.toml']) {
    errors.push('version: CLI runtime and pyproject versions must match');
  }

  const backendVersion = await readFile(resolve(repoRoot, 'backend/app/version.py'), 'utf8');
  if (parsePythonVersion(backendVersion) !== PRODUCT_VERSION) {
    errors.push(`version: backend product version must be ${PRODUCT_VERSION}`);
  }

  const openapi = await readJson(repoRoot, 'packages/api-sdk/openapi.json');
  if (openapi.info?.version !== PRODUCT_VERSION) {
    errors.push(`version: OpenAPI document must use product version ${PRODUCT_VERSION}`);
  }

  return errors;
}

export async function main(repoRoot = resolve(fileURLToPath(new URL('..', import.meta.url)))) {
  const errors = await collectReleaseContractErrors(repoRoot);
  if (errors.length > 0) {
    for (const error of errors) console.error(`- ${error}`);
    process.exitCode = 1;
    return;
  }
  console.log(`Release contract passed (GEOrank ${PRODUCT_VERSION}).`);
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  await main();
}
