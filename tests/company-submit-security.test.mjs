import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scriptPath = path.join(projectRoot, 'dist', 'js', 'company-submit-page.js');
const documentPath = path.join(projectRoot, 'dist', 'company-submit.html');

function createElement() {
  return {
    className: '',
    dataset: {},
    disabled: false,
    href: '',
    innerHTML: '',
    textContent: '',
    addEventListener() {},
    append() {},
    appendChild() {},
    classList: {
      add() {},
      contains() { return false; },
      remove() {},
      toggle() {}
    },
    querySelector() { return null; },
    querySelectorAll() { return []; }
  };
}

async function runSubmissionPage({companyId = '', token = '', url = 'https://www.xueersi.com', fetchImpl} = {}) {
  const source = await readFile(scriptPath, 'utf8');
  const elements = new Map();
  const storage = new Map(token ? [['georank_user_token', token]] : []);
  const authPrompts = [];
  let clearedSessions = 0;
  const documentListeners = new Map();
  const getElement = (id) => {
    if (!elements.has(id)) elements.set(id, createElement());
    return elements.get(id);
  };
  const document = {
    addEventListener(type, listener) {
      documentListeners.set(type, listener);
    },
    createElement,
    getElementById: getElement,
    querySelector() { return null; }
  };
  const window = {
    GEOrank: {
      Auth: {
        clearSession() {
          clearedSessions += 1;
          storage.delete('georank_user_token');
          storage.delete('georank_token');
        },
        requireAuth(options) {
          authPrompts.push(options);
          return false;
        }
      },
      Routes: {
        buildCompanySubmission() { return '/submit-company'; },
        readCompanySubmissionState() {
          return {companyId, url};
        }
      }
    },
    location: {
      hostname: 'localhost',
      pathname: '/submit-company',
      port: '3009',
      protocol: 'http:',
      search: '?url=https%3A%2F%2Fwww.xueersi.com'
    },
    setTimeout,
    clearTimeout
  };
  const fetchCalls = [];
  const context = vm.createContext({
    URL,
    URLSearchParams,
    clearTimeout,
    console,
    document,
    fetch: async (...args) => {
      fetchCalls.push(args);
      return fetchImpl
        ? fetchImpl(...args)
        : {ok: false, status: 401, json: async () => ({detail: '请先登录'})};
    },
    history: {replaceState() {}},
    localStorage: {
      getItem(key) { return storage.get(key) || null; },
      removeItem(key) { storage.delete(key); },
      setItem(key, value) { storage.set(key, String(value)); }
    },
    setTimeout,
    window
  });
  vm.runInContext(source, context);
  await new Promise((resolve) => setImmediate(resolve));
  return {
    authPrompts,
    get clearedSessions() { return clearedSessions; },
    documentListeners,
    elements,
    fetchCalls,
    storage
  };
}

test('anonymous company submission waits for login before creating an AI task', async () => {
  const result = await runSubmissionPage();

  assert.equal(result.fetchCalls.length, 0);
  assert.equal(result.authPrompts.length, 1);
  assert.match(result.authPrompts[0].reason, /登录后.*继续/);
  assert.match(result.elements.get('analysis-badge').innerHTML, /等待登录/);
});

test('company submission automatically continues after login succeeds', async () => {
  const result = await runSubmissionPage({
    fetchImpl: async (url) => {
      if (url.endsWith('/api/companies/submit')) {
        return {
          ok: true,
          status: 202,
          json: async () => ({
            company_id: 'company-id',
            normalized_url: 'https://www.xueersi.com',
            publish_status: 'draft',
            resumed: false,
            status: 'pending'
          })
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({
          company_id: 'company-id',
          progress: 100,
          publish_status: 'draft',
          selected_pages: [],
          status: 'completed'
        })
      };
    }
  });

  const authChanged = result.documentListeners.get('georank:auth-changed');
  assert.ok(authChanged);
  result.storage.set('georank_user_token', 'signed-in-token');
  authChanged({detail: {authenticated: true}});
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(result.fetchCalls.some(([url]) => url.endsWith('/api/companies/submit')));
});

test('authenticated company submission carries a stable device identifier', async () => {
  const result = await runSubmissionPage({token: 'signed-in-token'});

  const submitCall = result.fetchCalls.find(([url]) => url.endsWith('/api/companies/submit'));
  assert.ok(submitCall);
  const deviceId = submitCall[1].headers['X-GEOrank-Device-ID'];
  assert.ok(deviceId?.length >= 16);
  assert.equal(result.storage.get('georank_device_id_v1'), deviceId);
});

test('opening an existing company analysis asks the API to recover orphaned work', async () => {
  const result = await runSubmissionPage({
    companyId: 'existing-company-id',
    token: 'signed-in-token',
    fetchImpl: async (requestUrl) => {
      if (requestUrl.endsWith('/api/companies/submit')) {
        return {
          ok: true,
          status: 202,
          json: async () => ({
            company_id: 'existing-company-id',
            normalized_url: 'https://www.xueersi.com',
            publish_status: 'draft',
            resumed: true,
            status: 'pending'
          })
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({
          company_id: 'existing-company-id',
          progress: 100,
          publish_status: 'draft',
          selected_pages: [],
          status: 'completed'
        })
      };
    }
  });

  const submitCall = result.fetchCalls.find(([requestUrl]) => requestUrl.endsWith('/api/companies/submit'));
  assert.ok(submitCall);
  assert.deepEqual(JSON.parse(submitCall[1].body), {url: 'https://www.xueersi.com'});
});

test('expired company submission session returns to the login flow', async () => {
  const result = await runSubmissionPage({token: 'expired-token'});

  assert.equal(result.fetchCalls.length, 1);
  assert.equal(result.clearedSessions, 1);
  assert.equal(result.authPrompts.length, 1);
  assert.match(result.elements.get('analysis-badge').innerHTML, /等待登录/);
});

test('authentication refresh cannot create duplicate company submission requests', async () => {
  let resolveSubmit;
  const pendingSubmit = new Promise((resolve) => {
    resolveSubmit = resolve;
  });
  const result = await runSubmissionPage({
    token: 'signed-in-token',
    fetchImpl: async (url) => {
      if (url.endsWith('/api/companies/submit')) return pendingSubmit;
      return {ok: false, status: 500, json: async () => ({})};
    }
  });

  result.documentListeners.get('georank:auth-changed')?.({detail: {authenticated: true}});
  await new Promise((resolve) => setImmediate(resolve));
  const submitCalls = result.fetchCalls.filter(([url]) => url.endsWith('/api/companies/submit'));
  assert.equal(submitCalls.length, 1);

  resolveSubmit({ok: false, status: 500, json: async () => ({detail: 'stop'})});
  await new Promise((resolve) => setImmediate(resolve));
});

test('company submission return-home action stays on one line', async () => {
  const html = await readFile(documentPath, 'utf8');
  const match = html.match(/<a href="\/" class="([^"]+)"[^>]*>[\s\S]*?返回首页[\s\S]*?<\/a>/);

  assert.ok(match);
  const classes = new Set(match[1].split(/\s+/));
  assert.ok(classes.has('shrink-0'));
  assert.ok(classes.has('self-start'));
  assert.ok(classes.has('whitespace-nowrap'));
});

test('company submission page escapes crawler-controlled page metadata', async () => {
  const source = await readFile(scriptPath, 'utf8');

  assert.match(source, /function escapeHtml\(/);
  assert.match(source, /escapeHtml\(page\.title \|\| page\.url/);
  assert.match(source, /escapeHtml\(page\.reason/);
  assert.match(source, /escapeHtml\(page\.url/);
});

test('pipeline polling counts consecutive request failures only', async () => {
  const source = await readFile(scriptPath, 'utf8');

  assert.match(source, /async function pollPipeline\(companyId, consecutiveFailures = 0\)/);
  assert.match(source, /consecutiveFailures = 0;/);
  assert.match(source, /consecutiveFailures \+= 1;/);
  assert.doesNotMatch(source, /pollPipeline\(companyId, attempt \+ 1\)/);
});

test('failed pipeline does not fabricate completed stages', async () => {
  const source = await readFile(scriptPath, 'utf8');

  assert.match(source, /if \(status === 'failed'\) \{\s*setStepState\(stepName, 'failed'\)/);
});
