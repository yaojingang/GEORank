import {readdirSync, readFileSync, statSync} from 'node:fs';
import {join, relative} from 'node:path';

const roots = ['apps/web', 'apps/admin', 'packages/ui/src'];
const sourceExtensions = new Set(['.ts', '.tsx']);
const cjkPattern = /[\u4e00-\u9fff]/;
const ignoredDirectories = new Set(['.next', 'node_modules', 'dist', 'coverage']);

function extensionOf(filePath) {
  const dot = filePath.lastIndexOf('.');
  return dot >= 0 ? filePath.slice(dot) : '';
}

function walk(directory, files = []) {
  for (const entry of readdirSync(directory)) {
    if (ignoredDirectories.has(entry)) continue;
    const fullPath = join(directory, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      walk(fullPath, files);
    } else if (sourceExtensions.has(extensionOf(fullPath))) {
      files.push(fullPath);
    }
  }
  return files;
}

const findings = [];

for (const root of roots) {
  for (const filePath of walk(root)) {
    const content = readFileSync(filePath, 'utf8');
    const lines = content.split(/\r?\n/);
    lines.forEach((line, index) => {
      if (cjkPattern.test(line)) {
        findings.push({
          filePath: relative(process.cwd(), filePath),
          line: index + 1,
          text: line.trim()
        });
      }
    });
  }
}

if (findings.length) {
  console.error('Hardcoded CJK UI copy found outside packages/i18n dictionaries:');
  for (const finding of findings) {
    console.error(`${finding.filePath}:${finding.line} ${finding.text}`);
  }
  process.exit(1);
}

console.log('No hardcoded CJK UI copy found in apps/web, apps/admin, or packages/ui/src.');
