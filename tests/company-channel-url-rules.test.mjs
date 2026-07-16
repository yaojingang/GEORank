import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

async function read(relativePath) {
  return readFile(path.join(projectRoot, relativePath), 'utf8');
}

test('the static frontend reserves the root path for the homepage', async () => {
  const [runtime, header, nginx, companyPage, companySubmit, companyDirectory] = await Promise.all([
    read('dist/js/common.js'),
    read('dist/components/header.html'),
    read('infra/nginx/default.conf'),
    read('backend/app/web/company_pages.py'),
    read('dist/company-submit.html'),
    read('dist/index.html')
  ]);

  assert.match(
    runtime,
    /\{ key: 'companies', name: '公司', path: '\/companies', enabled: true, protected_paths: \['\/company', '\/companies', '\/c', '\/submit-company'\] \}/
  );
  assert.doesNotMatch(runtime, /modulePathToKey:\s*\{\s*'\/':\s*'companies'/);
  assert.match(runtime, /'\/companies': 'companies'/);
  assert.match(runtime, /normalized === '\/companies'[\s\S]*?return '\/companies';/);
  assert.match(runtime, /normalized === '\/submit-company'[\s\S]*?return '\/companies';/);
  assert.match(runtime, /return Routes\.buildUrl\('\/companies'\);/);
  assert.match(runtime, /companyListPath\(\)\s*\{\s*return this\.state\.homepage\?\.company_list_path \|\| '\/companies';\s*\}/);
  assert.match(runtime, /querySelectorAll\('\[data-logo-link\]'\)[\s\S]*?setAttribute\('href', '\/'\)/);

  const companyLinks = (header.match(/<a\b[^>]*>[\s\S]*?<\/a>/g) || [])
    .filter((anchor) => anchor.includes('data-i18n="nav.companies"'));
  assert.equal(companyLinks.length, 2);
  assert.ok(companyLinks.every((anchor) => anchor.includes('href="/companies"')));

  assert.match(nginx, /location = \/ \{[\s\S]*?try_files \/active\/index\.html @default_homepage;/);
  assert.match(nginx, /location @default_homepage \{\s*return 302 \/companies;/);
  assert.match(nginx, /location = \/index \{\s*return 301 \/companies\$is_args\$args;/);
  assert.match(nginx, /location = \/index\.html \{\s*return 301 \/companies\$is_args\$args;/);
  assert.match(nginx, /location = \/company \{[\s\S]*?if \(\$arg_id != ""\)[\s\S]*?return 301 \/companies\/\$arg_id;[\s\S]*?return 301 \/companies;/);
  assert.match(runtime, /normalizedPath === '\/company'[\s\S]*?Routes\.buildCompanyDetail\(params\.get\('id'\)\)[\s\S]*?Routes\.buildUrl\('\/companies'\)/);
  assert.match(
    runtime,
    /maybePromptFirstVisit\(\)[\s\S]*?path === '\/company'[\s\S]*?path === '\/companies'[\s\S]*?path\.startsWith\('\/c\/'\)[\s\S]*?return;/
  );
  assert.match(companyPage, /<a href="\/">首页<\/a><span>\/<\/span><a href="\/companies">公司<\/a>/);
  assert.match(companyPage, /"position": 2, "name": "公司", "item": _absolute_url\(request, "\/companies"\)/);
  assert.match(companySubmit, /<a href="\/companies"[^>]*>\s*返回公司首页\s*<\/a>/);
  assert.match(companyDirectory, /<link rel="canonical" href="\/companies">/);
});

test('the Next migration layer does not render the company directory at the root path', async () => {
  const [homePage, companiesPage] = await Promise.all([
    read('apps/web/app/[locale]/page.tsx'),
    read('apps/web/app/[locale]/companies/page.tsx')
  ]);

  assert.match(homePage, /notFound\(\)/);
  assert.doesNotMatch(homePage, /LegacyStaticPage|page="index"/);
  assert.match(companiesPage, /LegacyStaticPage page="index"/);
});
