import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {mkdtemp, readFile, readdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {dirname, join, relative, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {promisify} from 'node:util';

const execFileAsync = promisify(execFile);
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const packageRoot = resolve(repoRoot, 'packages/api-sdk');
const checkedInRoot = resolve(packageRoot, 'src/generated');

async function collectFiles(root, directory = root) {
  const files = new Map();
  for (const entry of await readdir(directory, {withFileTypes: true})) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      for (const [name, content] of await collectFiles(root, path)) files.set(name, content);
    } else if (entry.isFile()) {
      files.set(relative(root, path), await readFile(path, 'utf8'));
    }
  }
  return files;
}

const temporaryRoot = await mkdtemp(join(tmpdir(), 'georank-sdk-'));
try {
  await execFileAsync(
    'pnpm',
    [
      'exec',
      'openapi-ts',
      '-i',
      'openapi.json',
      '-o',
      temporaryRoot,
      '-c',
      '@hey-api/client-fetch',
    ],
    {cwd: packageRoot},
  );

  const [checkedIn, generated] = await Promise.all([
    collectFiles(checkedInRoot),
    collectFiles(temporaryRoot),
  ]);
  assert.deepEqual([...checkedIn.keys()].sort(), [...generated.keys()].sort(), 'Generated SDK file list is stale.');
  for (const [path, content] of generated) {
    assert.equal(checkedIn.get(path), content, `Generated SDK file is stale: ${path}`);
  }
  console.log('Generated API SDK matches packages/api-sdk/openapi.json.');
} finally {
  await rm(temporaryRoot, {recursive: true, force: true});
}
