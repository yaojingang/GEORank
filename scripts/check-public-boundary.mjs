#!/usr/bin/env node

import { execFileSync } from 'node:child_process';
import { lstatSync, readFileSync, readlinkSync, realpathSync } from 'node:fs';
import { isAbsolute, join, relative, resolve } from 'node:path';

import {
  decodeTextBufferCandidates,
  findSensitivePublicData,
  hasLegacyRepositoryReferenceInBuffer,
  isKnownBinaryPath,
  isPublicTextPath,
} from './public-content-policy.mjs';
import { collectPublicFileInventory } from './public-file-inventory.mjs';

const rootFlagIndex = process.argv.indexOf('--root');
const root = resolve(rootFlagIndex >= 0 ? process.argv[rootFlagIndex + 1] : process.cwd());
const canonicalRoot = realpathSync(root);
const allowInstalledDependencies = process.argv.includes('--allow-installed-dependencies');
const { entries: trackedEntries, mode: inventoryMode } = collectPublicFileInventory(root, {
  allowInstalledDependencies,
});
const trackedFiles = trackedEntries.map(({ path }) => path);
const trackedFileSet = new Set(trackedFiles);
const trackedModeByPath = new Map(trackedEntries.map(({ mode, path }) => [path, mode]));
const regularFileModes = new Set(['100644', '100755']);

const absoluteBlockedExtensions = new Set([
  '.bak', '.backup', '.db', '.dump', '.jks', '.key', '.p12', '.parquet', '.pem', '.pfx', '.sql',
  '.sqlite', '.sqlite3', '.xls', '.xlsx',
]);
const publicSampleExtensions = new Set(['.csv', '.jsonl']);
const homepageSourceExtensions = new Set([
  '.css', '.gif', '.htm', '.html', '.ico', '.jpeg', '.jpg', '.js', '.json', '.mjs',
  '.otf', '.png', '.svg', '.ttf', '.txt', '.webp', '.woff', '.woff2', '.xml',
]);
const blockedDirectoryNames = new Set([
  '.cache', '.longtask', '.mypy_cache', '.next', '.nox', '.pnpm-store', '.pytest_cache',
  '.ruff_cache', '.tox', '.venv', '__pycache__', 'backup', 'backups', 'cache', 'caches',
  'dump', 'dumps', 'node_modules', 'tmp', 'venv',
]);
function normalizePath(path) {
  return path.replaceAll('\\', '/').toLowerCase();
}

function isAllowedRuntimePath(normalized, name) {
  if (normalized === 'runtime/homepages/public/active') return true;
  if (normalized.startsWith('runtime/homepages/public/')) {
    const extension = name.includes('.') ? name.slice(name.lastIndexOf('.')) : '';
    return homepageSourceExtensions.has(extension);
  }
  if (/^runtime\/homepages\/releases\/[^/]+\/manifest\.json$/.test(normalized)) return true;
  if (!/^runtime\/homepages\/releases\/[^/]+\/source\/.+/.test(normalized)) return false;
  const extension = name.includes('.') ? name.slice(name.lastIndexOf('.')) : '';
  return homepageSourceExtensions.has(extension);
}

function activeHomepageTargetReason(target) {
  if (target !== target.trim()) return 'target contains surrounding whitespace';
  const match = target.match(/^releases\/([a-z0-9][a-z0-9._-]*)$/i);
  if (!match) return 'target must be a relative releases/<safe-release-id> path';
  const releaseId = match[1];
  const publicEntry = `runtime/homepages/public/releases/${releaseId}/index.html`;
  const manifest = `runtime/homepages/releases/${releaseId}/manifest.json`;
  if (!trackedFileSet.has(publicEntry) || !trackedFileSet.has(manifest)) {
    return 'target release entry and manifest must both be tracked';
  }
  return null;
}

function symlinkTargetReason(path, target) {
  if (target !== target.trim()) return 'target contains surrounding whitespace';
  if (target.length === 0) return 'target is empty';
  if (isAbsolute(target)) return 'target must be relative';
  const sourceDirectory = resolve(root, path, '..');
  const targetPath = resolve(sourceDirectory, target);
  const relativeTarget = relative(root, targetPath);
  if (relativeTarget === '..' || relativeTarget.startsWith(`..${process.platform === 'win32' ? '\\' : '/'}`)) {
    return 'target escapes the source root';
  }
  if (!lstatSync(targetPath, { throwIfNoEntry: false })) return 'target does not exist';
  let canonicalTarget;
  try {
    canonicalTarget = realpathSync(targetPath);
  } catch {
    return 'target cannot be resolved';
  }
  const canonicalRelativeTarget = relative(canonicalRoot, canonicalTarget);
  if (
    canonicalRelativeTarget === '..'
    || canonicalRelativeTarget.startsWith(`..${process.platform === 'win32' ? '\\' : '/'}`)
  ) {
    return 'target escapes the source root through another link';
  }
  return null;
}

function requiresRegularRuntimeFile(path) {
  const normalized = normalizePath(path);
  if (normalized === 'runtime/homepages/public/active') return false;
  return normalized.startsWith('runtime/homepages/public/')
    || /^runtime\/homepages\/releases\/[^/]+\/(?:manifest\.json|source\/)/.test(normalized);
}

function forbiddenPathReason(path) {
  const slashNormalized = path.replaceAll('\\', '/');
  const normalized = normalizePath(path);
  const parts = normalized.split('/');
  const name = parts.at(-1);
  const directories = parts.slice(0, -1);
  const isPublicDataAsset = [
    'assets/public/',
    'data/public/',
    'public/assets/',
    'public/data/',
    'runtime/homepages/public/',
  ].some((prefix) => normalized.startsWith(prefix));
  if (normalized.startsWith('runtime/') && slashNormalized !== normalized) {
    return 'noncanonical runtime path casing';
  }
  if (name.startsWith('.env') && name !== '.env.example') return 'environment file';
  if (normalized.startsWith('runtime/') && !isAllowedRuntimePath(normalized, name)) {
    return 'private runtime state';
  }
  if (parts.some((part) => /(?:^|[-_.\s])private(?:$|[-_.\s])/.test(part))) return 'private path token';
  if (directories.some((part) => /(?:^|[-_])wiki(?:[-_]|$)/.test(part))) return 'private wiki source';
  if (normalized.startsWith('runtime/data/')) return 'runtime data';
  if (normalized.startsWith('dist/images/tutorial/')) return 'private tutorial image';
  if (parts.some((part) => blockedDirectoryNames.has(part))) return 'private or generated directory';
  const extension = name.includes('.') ? name.slice(name.lastIndexOf('.')) : '';
  if (absoluteBlockedExtensions.has(extension)) return 'runtime data or backup';
  if (publicSampleExtensions.has(extension) && !isPublicDataAsset) return 'runtime data or backup';
  if (
    /(?:admin|private|credential|session)[-_ ]*(?:screen(?:shot)?|capture)|(?:screen(?:shot)?|capture)[-_ ]*(?:admin|private|credential|session)/i.test(name)
    && /\.(?:gif|jpe?g|png|webp)$/i.test(name)
  ) return 'private screenshot';
  return null;
}

function isPlaceholder(value) {
  const normalized = value.trim().toLowerCase();
  if (normalized.length === 0) return true;
  if (/^\$\{[a-z_][a-z0-9_]*\}$/i.test(normalized)) return true;
  const environmentRequired = normalized.match(/^\$\{[a-z_][a-z0-9_]*:\?([^{}]+)\}$/i);
  if (environmentRequired) return isPlaceholder(environmentRequired[1]);
  const environmentFallback = normalized.match(/^\$\{[a-z_][a-z0-9_]*:-([^{}]+)\}$/i);
  if (environmentFallback) return isPlaceholder(environmentFallback[1]);
  if (/^process\.env\.[a-z_][a-z0-9_]*$/i.test(normalized)) return true;
  if (/^os\.getenv\(\s*["'][a-z_][a-z0-9_]*["']\s*\)$/i.test(normalized)) return true;
  if (/^settings\.[a-z_][a-z0-9_]*$/i.test(normalized)) return true;
  if (/^sk-test-[a-z0-9_-]{16,}$/i.test(normalized)) return true;
  return /^(?:change[-_]?me|changeme|dummy|example|fake|placeholder|replace[-_]?me|sample|test|your)(?:[-_ ][a-z0-9]+)*$/i.test(normalized);
}

function hasHighConfidenceSecret(path, text) {
  const specificSecretPatterns = [
    new RegExp(`sk-${'[A-Za-z0-9_-]{24,}'}`, 'g'),
    new RegExp(`gh[pousr]_${'[A-Za-z0-9]{30,}'}`, 'g'),
    new RegExp(`github_pat_${'[A-Za-z0-9_]{40,}'}`, 'g'),
    new RegExp(`AKIA${'[A-Z0-9]{16}'}`, 'g'),
    new RegExp(`AIza${'[A-Za-z0-9_-]{30,}'}`, 'g'),
    /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{20,}\b/g,
    /\bADMIN_(?:JWT|SESSION)(?:_TOKEN)?\s*[:=]\s*["'`]?[A-Za-z0-9._-]{24,}/g,
    /-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----/g,
  ];
  for (const pattern of specificSecretPatterns) {
    for (const match of text.matchAll(pattern)) {
      if (!isPlaceholder(match[0])) return true;
    }
  }

  const credentialName = String.raw`(?:[A-Za-z][A-Za-z0-9_-]*[_-])?(?:api[_-]?key|password|token|secret|secret[_-]?key|master[_-]?key|fernet[_-]?key|cookie|(?:admin[_-]?)?session[_-]?(?:id|cookie)|settings[_-]?encryption[_-]?key|encryption[_-]?key|private[_-]?key)`;
  const assignmentPatterns = [
    new RegExp(String.raw`(?:\b${credentialName}\b|["'\x60]${credentialName}["'\x60])[ \t]*[:=][ \t]*(["'\x60])([^"'\x60\r\n]+)\1`, 'gi'),
  ];
  const configPath = path.toLowerCase();
  if (/(?:^|\/)(?:\.env(?:\.[^/]*)?|[^/]+\.(?:env|ya?ml|toml|ini|cfg|conf|properties))$/.test(configPath)) {
    assignmentPatterns.push(
      new RegExp(String.raw`(?:^|\r?\n)[ \t]*(?:-[ \t]*)?(?:${credentialName}|["']${credentialName}["'])[ \t]*[:=][ \t]*([^\s#"'\x60]+)`, 'gi'),
    );
  }
  for (const assignmentPattern of assignmentPatterns) {
    for (const match of text.matchAll(assignmentPattern)) {
      const value = match[2] ?? match[1];
      if (isPlaceholder(value) || value.length < 20 || /\s/.test(value)) continue;
      const characterClasses = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/]
        .filter((pattern) => pattern.test(value)).length;
      if (characterClasses >= 2) return true;
    }
  }
  return false;
}

function hasHardCodedSeedAdminPassword(path, text) {
  if (!/(?:^|\/)(?:[^/]*seed[^/]*|fixtures?)(?:\/|\.|$)/i.test(path)) return false;
  const patterns = [
    /(?:ADMIN(?:_SEED)?_PASSWORD|admin_password)\s*=\s*["']([^"']+)["']/gi,
    /(?:ADMIN(?:_SEED)?_PASSWORD|admin_password)\s*=\s*`([^`]+)`/gi,
    /["']password["']\s*:\s*["']([^"']+)["']/gi,
  ];
  for (const pattern of patterns) {
    for (const match of text.matchAll(pattern)) {
      if (!isPlaceholder(match[1])) return true;
    }
  }
  return false;
}

function hasPrivateKnowledgeLink(text) {
  const feishuHost = ['feishu', 'cn'].join('\\.');
  const wikiSegment = ['wi', 'ki'].join('');
  const feishuPattern = new RegExp(`https?:\\/\\/[^\\s"'<>]*${feishuHost}(?:\\/[^\\s"'<>]*)?`, 'i');
  const githubWikiPattern = new RegExp(`https?:\\/\\/github\\.com\\/[^\\s"'<>]+\\/${wikiSegment}(?:[\\/?#][^\\s"'<>]*)?`, 'i');
  return feishuPattern.test(text) || githubWikiPattern.test(text);
}

const violations = new Set();
for (const path of trackedFiles) {
  const normalizedPath = normalizePath(path);
  const pathReason = forbiddenPathReason(path);
  if (pathReason) violations.add(`forbidden path: ${path} (${pathReason})`);
  if (requiresRegularRuntimeFile(path) && !regularFileModes.has(trackedModeByPath.get(path))) {
    violations.add(`invalid runtime homepage file: ${path} (index mode must be a regular file)`);
  }

  const absolutePath = join(root, path);
  const stats = lstatSync(absolutePath, { throwIfNoEntry: false });
  const indexBuffer = inventoryMode === 'git'
    ? execFileSync('git', ['show', `:${path}`], {
      cwd: root,
      encoding: null,
      maxBuffer: 64 * 1024 * 1024,
    })
    : stats?.isSymbolicLink()
      ? Buffer.from(readlinkSync(absolutePath))
      : readFileSync(absolutePath);
  const buffers = [indexBuffer];
  if (trackedModeByPath.get(path) === '120000') {
    const targetReason = symlinkTargetReason(path, indexBuffer.toString('utf8'));
    if (targetReason) violations.add(`unsafe symlink: ${path} (${targetReason})`);
  }
  if (normalizedPath === 'runtime/homepages/public/active') {
    if (trackedModeByPath.get(path) !== '120000') {
      violations.add(`invalid homepage active symlink: ${path} (index mode must be 120000)`);
    }
    const targetReason = activeHomepageTargetReason(indexBuffer.toString('utf8'));
    if (targetReason) violations.add(`invalid homepage active symlink: ${path} (${targetReason})`);
  }
  if (!stats && normalizedPath === 'runtime/homepages/public/active') {
    violations.add(`missing runtime homepage file: ${path} (working active symlink is required)`);
  }
  if (!stats && requiresRegularRuntimeFile(path)) {
    violations.add(`missing runtime homepage file: ${path} (working regular file is required)`);
  }
  if (stats) {
    if (normalizedPath === 'runtime/homepages/public/active' && !stats.isSymbolicLink()) {
      violations.add(`invalid homepage active symlink: ${path} (working copy must be a symlink)`);
    }
    if (requiresRegularRuntimeFile(path) && !stats.isFile()) {
      violations.add(`invalid runtime homepage file: ${path} (working copy must be a regular file)`);
    }
    if (!stats.isDirectory()) {
      const workingBuffer = stats.isSymbolicLink()
        ? Buffer.from(readlinkSync(absolutePath))
        : readFileSync(absolutePath);
      if (stats.isSymbolicLink()) {
        const targetReason = symlinkTargetReason(path, workingBuffer.toString('utf8'));
        if (targetReason) violations.add(`unsafe symlink: ${path} (${targetReason})`);
      }
      if (normalizedPath === 'runtime/homepages/public/active') {
        const targetReason = activeHomepageTargetReason(workingBuffer.toString('utf8'));
        if (targetReason) {
          violations.add(`invalid homepage active symlink: ${path} (${targetReason})`);
        }
      }
      if (!workingBuffer.equals(indexBuffer)) buffers.push(workingBuffer);
    }
  }

  for (const buffer of buffers) {
    if (hasLegacyRepositoryReferenceInBuffer(buffer)) {
      violations.add(`legacy repository reference: ${path}`);
    }
    if (buffer.includes(0) && !isKnownBinaryPath(path)) {
      violations.add(`NUL byte in ${isPublicTextPath(path) ? 'public text' : 'text'}: ${path}`);
    }
    for (const text of decodeTextBufferCandidates(buffer)) {
      if (isPublicTextPath(path)) {
        let publicContent = text;
        if (/\.json$/i.test(path)) {
          try {
            publicContent = JSON.parse(text);
          } catch {
            // Scan malformed or differently encoded public fixtures as text.
          }
        }
        if (findSensitivePublicData(publicContent).length > 0) {
          violations.add(`sensitive public data: ${path}`);
        }
      }
      if (hasHighConfidenceSecret(path, text)) violations.add(`high-confidence secret: ${path}`);
      if (hasHardCodedSeedAdminPassword(path, text)) {
        violations.add(`hard-coded seed admin password: ${path}`);
      }
      if (hasPrivateKnowledgeLink(text)) violations.add(`private knowledge link: ${path}`);
    }
  }
}

if (violations.size > 0) {
  console.error('Public boundary check failed:');
  for (const violation of violations) console.error(`- ${violation}`);
  process.exitCode = 1;
} else {
  console.log(`Public boundary check passed (${trackedFiles.length} files, ${inventoryMode} mode).`);
}
