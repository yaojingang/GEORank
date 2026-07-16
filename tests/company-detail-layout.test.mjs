import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const companyPagePath = path.join(projectRoot, 'backend', 'app', 'web', 'company_pages.py');
const companyCssPath = path.join(projectRoot, 'dist', 'css', 'company.css');

async function loadCompanyPageFiles() {
  const [pageSource, css] = await Promise.all([
    readFile(companyPagePath, 'utf8'),
    readFile(companyCssPath, 'utf8')
  ]);
  const renderStart = pageSource.indexOf('def _render_page(');
  const routeStart = pageSource.indexOf('@router.get("/c/{company_identifier}"');
  return {
    pageSource,
    renderSource: pageSource.slice(renderStart, routeStart),
    css
  };
}

test('company detail prioritizes the approved public company profile architecture', async () => {
  const {pageSource, renderSource} = await loadCompanyPageFiles();

  for (const sectionId of [
    'company-profile',
    'company-story',
    'company-capabilities',
    'company-team',
    'company-sources',
    'company-geo'
  ]) {
    assert.match(pageSource, new RegExp(`id="${sectionId}"`));
  }

  for (const heading of [
    '公司介绍',
    '业务与能力',
    '团队与信任',
    '公开资料与可信信号',
    'GEO 分析'
  ]) {
    assert.match(pageSource, new RegExp(heading));
  }

  for (const removedHeading of [
    'GEO 行动计划',
    'Phase 01',
    '页面可读性摘要',
    '知识库概览',
    '资料完备清单',
    'AI 读取信号矩阵',
    '来源结构优先级',
    '技术与内容资产'
  ]) {
    assert.doesNotMatch(renderSource, new RegExp(removedHeading));
  }

  assert.match(renderSource, /company-profile-nav/);
  assert.match(pageSource, /def _company_story_markup/);
  assert.match(pageSource, /def _business_capabilities_markup/);
});

test('sparse company data collapses instead of rendering oversized empty modules', async () => {
  const {pageSource, renderSource} = await loadCompanyPageFiles();

  assert.match(pageSource, /def _semantic_map_markup[\s\S]*?if len\(nodes\) < 4:[\s\S]*?company-semantic-terms/);
  assert.match(pageSource, /def _similar_companies_section_markup[\s\S]*?if not companies:[\s\S]*?return ""/);
  assert.match(pageSource, /def _team_profile_section_markup[\s\S]*?if not members:[\s\S]*?return ""/);
  assert.match(pageSource, /def _public_sources_section_markup[\s\S]*?if not pages:[\s\S]*?return ""/);
  assert.match(pageSource, /_PUBLIC_PLACEHOLDER_VALUES/);
  assert.match(pageSource, /def _public_record_list/);
  assert.match(pageSource, /def _public_team_members/);
  assert.match(pageSource, /def _public_source_pages/);
  assert.match(pageSource, /def _geo_priority[\s\S]*?return None, None/);
  assert.match(renderSource, /tags = \[[\s\S]*?_public_profile_value\(value\)[\s\S]*?tech_stack = \[/);
  assert.doesNotMatch(pageSource, /\("citation", "外部背书"/);
  assert.match(pageSource, /def _source_evidence_markup[\s\S]*?_public_profile_value\(page\.get\("role"\)\)[\s\S]*?_public_profile_value\(page\.get\("reason"\)\)/);
  assert.match(pageSource, /except \(TypeError, ValueError, OverflowError\):/);
  assert.match(renderSource, /\{similar_section_html\}/);
  assert.match(renderSource, /\{team_section_html\}/);
  assert.match(renderSource, /\{public_sources_section_html\}/);
});

test('company detail reuses the diagnostic visual system and stays readable on mobile', async () => {
  const {renderSource, css} = await loadCompanyPageFiles();

  assert.match(css, /--company-primary:\s*#2563eb;/);
  assert.match(css, /--company-border:\s*#f1f5f9;/);
  assert.match(css, /\.company-page-content\s*\{[^}]*width:\s*min\(100%,\s*80rem\);/s);
  assert.match(css, /\.company-page\s*\{[^}]*font-family:\s*"Inter"/s);
  assert.match(css, /\.company-primary-action\s*\{[^}]*border-radius:\s*var\(--company-radius-button\);/s);
  assert.doesNotMatch(css, /box-shadow\s*:/);
  assert.match(css, /\.company-profile-nav\s*\{[^}]*overflow-x:\s*auto;/s);
  assert.match(css, /\.company-profile-nav a\s*\{[^}]*min-height:\s*2\.75rem;/s);
  assert.match(css, /\.company-term\s*\{[^}]*max-width:\s*100%;[^}]*overflow-wrap:\s*anywhere;/s);
  assert.match(css, /\.company-tool-term\s*\{[^}]*max-width:\s*100%;[^}]*overflow-wrap:\s*anywhere;/s);
  assert.match(css, /\.company-geo-semantic\s*\{[^}]*padding:\s*2rem;/s);

  assert.match(
    css,
    /\.company-hero-layout\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1\.55fr\)\s+minmax\(20rem,\s*0\.75fr\);/s
  );
  assert.match(
    css,
    /\.company-source-item\s*\{[^}]*grid-template-columns:\s*3rem\s+minmax\(0,\s*1fr\);/s
  );
  assert.match(
    css,
    /@media\s*\(max-width:\s*767px\)[\s\S]*?\.company-hero-layout,[\s\S]*?\.company-capabilities-layout\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\);/s
  );
  assert.doesNotMatch(renderSource, /来源强度/);
});

test('company detail exposes keyboard navigation and motion-safe interactions', async () => {
  const {renderSource, css} = await loadCompanyPageFiles();

  assert.match(renderSource, /class="company-skip-link" href="#company-profile"/);
  assert.match(css, /:focus-visible/);
  assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  assert.doesNotMatch(css, /transition:\s*all\b/);
});
