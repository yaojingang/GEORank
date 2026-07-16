import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const indexHtmlPath = path.join(projectRoot, 'dist', 'index.html');
const indexJsPath = path.join(projectRoot, 'dist', 'js', 'index.js');
const companiesRoutePath = path.join(projectRoot, 'backend', 'app', 'api', 'routes', 'companies.py');

async function loadHomepageFiles() {
  const [html, js] = await Promise.all([
    readFile(indexHtmlPath, 'utf8'),
    readFile(indexJsPath, 'utf8')
  ]);
  const cardStart = js.indexOf('function renderCompanyCard(company)');
  const cardEnd = js.indexOf('function updateSortButtons()', cardStart);
  return {html, js, cardSource: js.slice(cardStart, cardEnd)};
}

test('company cards show the real detail-page view count without a PV label', async () => {
  const {cardSource} = await loadHomepageFiles();

  assert.match(cardSource, /company\.view_count/);
  assert.match(cardSource, /visibility/);
  assert.doesNotMatch(cardSource, /PV/);
  assert.doesNotMatch(cardSource, /company\.upvotes/);
  assert.doesNotMatch(cardSource, /用户投票功能即将开放/);
  assert.doesNotMatch(cardSource, /disabled/);
});

test('historical hot lists request companies ordered by page views', async () => {
  const [{html, js}, companiesRoute] = await Promise.all([
    loadHomepageFiles(),
    readFile(companiesRoutePath, 'utf8')
  ]);

  assert.match(html, /id="company-sort-views"/);
  assert.match(html, /data-company-sort="views"/);
  assert.match(js, /sortViews/);
  assert.match(js, /sort=views/);
  assert.doesNotMatch(html, /data-company-sort="upvotes"/);
  assert.match(
    companiesRoute,
    /Company\.view_count\.desc\(\),\s*Company\.created_at\.desc\(\),\s*Company\.id\.asc\(\)/
  );
  assert.match(companiesRoute, /query\.order_by\(None\)\.subquery\(\)/);
});

test('company directory sort controls expose selected state and usable touch targets', async () => {
  const [{html, js}, commonCss] = await Promise.all([
    loadHomepageFiles(),
    readFile(path.join(projectRoot, 'dist', 'css', 'common.css'), 'utf8')
  ]);

  assert.match(html, /data-company-sort="newest"[^>]*aria-pressed="true"/);
  assert.match(html, /data-company-sort="views"[^>]*aria-pressed="false"/);
  assert.match(html, /data-company-sort-indicator/);
  assert.match(js, /setAttribute\('aria-pressed', String\(isActive\)\)/);
  assert.match(js, /data-company-sort-indicator/);
  assert.match(commonCss, /\.company-sort-control\s*\{[^}]*min-height:\s*2\.75rem;/s);
  assert.match(commonCss, /\.company-card-link\s*\{[^}]*min-height:\s*2\.75rem;/s);
});

test('company directory hides placeholder data and wraps long tags', async () => {
  const [{js}, commonCss] = await Promise.all([
    loadHomepageFiles(),
    readFile(path.join(projectRoot, 'dist', 'css', 'common.css'), 'utf8')
  ]);

  assert.match(js, /PUBLIC_PLACEHOLDER_VALUES/);
  assert.match(js, /function publicProfileValue/);
  assert.match(js, /company\.tags\.map\(publicProfileValue\)/);
  assert.match(commonCss, /\.tag\s*\{[^}]*max-width:\s*100%;[^}]*overflow-wrap:\s*anywhere;/s);
});
