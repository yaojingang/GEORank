import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = path.resolve(import.meta.dirname, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

test('Docker production serves the quota-aware static applications after migrations', () => {
  const compose = read('docker-compose.yml');
  assert.match(compose, /\.\/dist:\/usr\/share\/nginx\/html/);
  assert.match(compose, /migrate:[\s\S]*app\.scripts\.migrate/);
  assert.match(compose, /api:[\s\S]*migrate:[\s\S]*service_completed_successfully/);
  assert.match(compose, /worker:[\s\S]*migrate:[\s\S]*service_completed_successfully/);
  assert.match(compose, /crawler:[\s\S]*migrate:[\s\S]*service_completed_successfully/);
});

test('shared static frontend carries device identity and backend-controlled BYOK policy', () => {
  const common = read('dist/js/common.js');
  assert.match(common, /X-GEOrank-Device-ID/);
  assert.match(common, /\/api\/usage\/policy/);
  assert.match(common, /allowed_byok_providers/);
  assert.match(common, /byok_guidance/);
  assert.match(common, /allow_user_byok === false/);
  assert.match(common, /isAllowedProviderConfig/);
  assert.match(common, /new URL\(config\.baseUrl\)\.origin/);
  assert.match(common, /isSensitiveContext/);
  assert.match(common, /form\.provider\.replaceChildren/);
  assert.doesNotMatch(common, /form\.provider\.innerHTML/);
  assert.doesNotMatch(common, /<option value="custom">自定义 OpenAI-compatible<\/option>/);
});

test('live static admin exposes lifetime, global, guidance and per-user quota controls', () => {
  const settings = read('dist/admin/settings.html');
  const admin = read('dist/js/admin.js');
  assert.match(settings, /终身赠送额度/);
  assert.match(settings, /全站每日 Token 阈值/);
  assert.match(settings, /用户自备 API 引导/);
  assert.doesNotMatch(settings, /value="daily_quota"/);
  assert.doesNotMatch(settings, /value="quota_with_byok"/);
  assert.doesNotMatch(settings, /value="browser_direct"/);
  assert.match(admin, /\/api\/admin\/api-policy/);
  assert.match(admin, /\/ai-quota/);
  assert.match(admin, /lifetime_token_grant/);
  assert.match(admin, /global_daily_token_limit/);
});

test('live profile renders lifetime and global usage with async BYOK boundary', () => {
  const html = read('dist/profile.html');
  const script = read('dist/js/profile.js');
  assert.match(html, /终身赠送剩余/);
  assert.match(html, /全站今日预算/);
  assert.match(html, /后台异步任务/);
  assert.match(script, /lifetime_quota_with_byok/);
  assert.match(script, /global_budget/);
  assert.match(script, /provider_presets/);
  assert.match(script, /APIKeyStore\?\.applyPolicy/);
  assert.match(script, /form\.provider\.replaceChildren/);
  assert.doesNotMatch(script, /form\.provider\.innerHTML/);
});
