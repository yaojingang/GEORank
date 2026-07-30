import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

const root = path.resolve(import.meta.dirname, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

function loadStaticApiKeyStore() {
  const common = read('dist/js/common.js');
  const start = common.indexOf('const APIKeyStore = {');
  const end = common.indexOf('window.GEOrank.APIKeyStore = APIKeyStore;', start);
  assert.ok(start >= 0 && end > start, 'could not isolate the deployed API key store');

  const storage = new Map();
  const context = {
    Auth: {
      apiBase: '',
      clearCookie() {},
      getCookie() { return ''; },
      showToast() {},
    },
    CustomEvent: class CustomEvent {
      constructor(type, init) {
        this.type = type;
        this.detail = init?.detail;
      }
    },
    DeviceIdentity: {
      getHeaders() {
        return {'X-GEOrank-Device-ID': 'device-1234567890'};
      },
    },
    URL,
    document: {
      dispatchEvent() {},
    },
    localStorage: {
      getItem(key) {
        return storage.get(key) ?? null;
      },
      removeItem(key) {
        storage.delete(key);
      },
      setItem(key, value) {
        storage.set(key, value);
      },
    },
    window: {
      GEOrank: {},
      location: {
        hostname: 'localhost',
        port: '3009',
        protocol: 'http:',
      },
    },
  };
  vm.runInNewContext(
    `${common.slice(start, end)}window.GEOrank.APIKeyStore = APIKeyStore;`,
    context
  );
  return context.window.GEOrank.APIKeyStore;
}

function loadProfileProviderResolver() {
  const profile = read('dist/js/profile.js');
  const start = profile.indexOf('function resolveProfileProviderConfig(');
  const end = profile.indexOf('function showMessage(', start);
  assert.ok(start >= 0 && end > start, 'could not isolate the profile provider resolver');
  const context = {};
  vm.runInNewContext(
    `${profile.slice(start, end)}this.resolveProfileProviderConfig = resolveProfileProviderConfig;`,
    context
  );
  return context.resolveProfileProviderConfig;
}

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

test('profile usage hydration keeps approved providers available for saving', () => {
  const store = loadStaticApiKeyStore();
  const provider = {
    key: 'deepseek',
    name: 'DeepSeek',
    base_url: 'https://api.deepseek.com',
    default_model: 'deepseek-chat',
  };

  store.applyPolicy({
    allow_user_byok: true,
    allowed_byok_providers: [provider],
  });
  store.applyPolicy({
    allow_user_byok: true,
    provider_presets: [provider],
  });

  const saved = store.save({
    enabled: true,
    provider: 'deepseek',
    baseUrl: 'https://api.deepseek.com',
    model: 'deepseek-chat',
    apiKey: 'sk-user',
  });

  assert.equal(saved.provider, 'deepseek');
  assert.equal(saved.baseUrl, 'https://api.deepseek.com');
  assert.equal(store.hasUsableKey(), true);
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

test('live static admin manages approved BYOK providers with common templates', () => {
  const settings = read('dist/admin/settings.html');
  const admin = read('dist/js/admin.js');

  assert.match(settings, /id="api-policy-provider-template"/);
  assert.match(settings, /id="api-policy-provider-add"/);
  assert.match(settings, /id="api-policy-provider-list"/);
  assert.match(settings, /value="deepseek"/);
  assert.match(settings, /value="openrouter"/);
  assert.match(settings, /value="siliconflow"/);
  assert.match(settings, /value="qwen"/);
  assert.match(settings, /value="openai-compatible"/);
  assert.match(admin, /collectByokProvidersFromDom/);
  assert.match(admin, /renderByokProviders/);
  assert.match(admin, /const allowedByokProviders = collectByokProvidersFromDom\(\)/);
  assert.match(admin, /allowed_byok_providers:\s*allowedByokProviders/);
  assert.match(admin, /guidanceProviderIndex/);
  assert.doesNotMatch(admin, /providers\.slice\(0,\s*12\)/);
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
  assert.match(script, /translated !== key/);
});

test('profile keeps provider, Base URL and model on the same approved preset', () => {
  const resolveProvider = loadProfileProviderResolver();
  const providers = [
    {
      key: 'deepseek',
      name: 'DeepSeek',
      base_url: 'https://api.deepseek.com',
      default_model: 'deepseek-v4-flash',
    },
    {
      key: 'openrouter',
      name: 'OpenRouter',
      base_url: 'https://openrouter.ai/api/v1',
      default_model: '~openai/gpt-latest',
    },
  ];

  const guided = resolveProvider(
    providers,
    {provider: 'openrouter', base_url: 'https://openrouter.ai/api/v1', model: '~openai/gpt-latest'},
    {}
  );
  assert.equal(guided.provider, 'openrouter');
  assert.equal(guided.baseUrl, 'https://openrouter.ai/api/v1');
  assert.equal(guided.model, '~openai/gpt-latest');

  const revoked = resolveProvider(
    providers,
    {provider: 'openrouter'},
    {provider: 'removed-provider', baseUrl: 'https://removed.example/v1', model: 'old', apiKey: 'secret'}
  );
  assert.equal(revoked.provider, 'openrouter');
  assert.equal(revoked.baseUrl, 'https://openrouter.ai/api/v1');
  assert.equal(revoked.apiKey, '');

  assert.match(read('dist/js/profile.js'), /(?:apiForm|form)\.provider\.addEventListener\('change'/);
});
