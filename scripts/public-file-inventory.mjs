import { execFileSync, spawnSync } from 'node:child_process';
import { lstatSync, readdirSync, realpathSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

const archiveDependencyDirectories = new Set([
  'node_modules',
  'apps/admin/node_modules',
  'apps/web/node_modules',
  'packages/api-sdk/node_modules',
  'packages/auth/node_modules',
  'packages/i18n/node_modules',
  'packages/ui/node_modules',
]);

function normalizeRelativePath(path) {
  return path.replaceAll('\\', '/');
}

function gitRoot(root) {
  const result = spawnSync('git', ['rev-parse', '--show-toplevel'], {
    cwd: root,
    encoding: 'utf8',
  });
  if (result.status !== 0) return null;
  return resolve(result.stdout.trim());
}

function collectGitEntries(root) {
  return execFileSync('git', ['ls-files', '-s', '-z'], {
    cwd: root,
    encoding: 'utf8',
  }).split('\0').filter(Boolean).map((entry) => {
    const separator = entry.indexOf('\t');
    if (separator < 0) throw new Error(`Malformed Git index entry: ${entry}`);
    const [mode] = entry.slice(0, separator).split(' ');
    return { mode, path: entry.slice(separator + 1) };
  });
}

function collectArchiveEntries(root, allowInstalledDependencies) {
  const entries = [];

  function walk(directory) {
    for (const directoryEntry of readdirSync(directory, { withFileTypes: true })) {
      if (directoryEntry.name === '.git') {
        throw new Error('Archive mode refuses embedded .git metadata');
      }
      const absolutePath = join(directory, directoryEntry.name);
      const path = normalizeRelativePath(relative(root, absolutePath));
      if (
        allowInstalledDependencies
        && directoryEntry.isDirectory()
        && archiveDependencyDirectories.has(path)
      ) continue;
      const stats = lstatSync(absolutePath);
      if (stats.isDirectory()) {
        walk(absolutePath);
      } else if (stats.isFile()) {
        entries.push({ mode: stats.mode & 0o111 ? '100755' : '100644', path });
      } else if (stats.isSymbolicLink()) {
        entries.push({ mode: '120000', path });
      } else {
        throw new Error(`Archive mode refuses unsupported filesystem entry: ${path}`);
      }
    }
  }

  walk(root);
  entries.sort((left, right) => left.path.localeCompare(right.path));
  return entries;
}

export function collectPublicFileInventory(rootPath, { allowInstalledDependencies = false } = {}) {
  const root = resolve(rootPath);
  const canonicalRoot = realpathSync(root);
  const metadata = lstatSync(join(root, '.git'), { throwIfNoEntry: false });
  const detectedGitRoot = gitRoot(root);

  if (metadata) {
    if (!detectedGitRoot || realpathSync(detectedGitRoot) !== canonicalRoot) {
      throw new Error('Git metadata exists but rev-parse did not resolve the requested repository root');
    }
    return { entries: collectGitEntries(root), mode: 'git', root };
  }

  if (detectedGitRoot && realpathSync(detectedGitRoot) === canonicalRoot) {
    throw new Error('Git rev-parse resolved the requested root without local .git metadata');
  }

  return {
    entries: collectArchiveEntries(root, allowInstalledDependencies),
    mode: 'archive',
    root,
  };
}
