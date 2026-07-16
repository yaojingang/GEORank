import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

test('static user center uses the approved ordered information architecture', () => {
  const html = read('dist/profile.html');

  assert.match(html, /data-profile-summary/);
  assert.match(html, /class="profile-stack"/);
  assert.match(html, /data-profile-api-panel/);
  assert.match(html, /data-profile-settings-panel/);
  assert.match(html, /data-profile-account-form/);
  assert.match(html, /data-i18n="profile\.modelApiTitle"/);
  assert.match(html, /data-i18n="profile\.accountSecurity"/);
  assert.doesNotMatch(html, /profile-card--settings(?:"|\s)/);
  assert.doesNotMatch(html, /profile-card--shortcuts/);
});

test('static header sends signed-out users to login and signed-in users to profile', () => {
  const common = read('dist/js/common.js');

  assert.match(common, /<a href="\/login" data-auth-trigger data-profile-link/);
  assert.match(common, /trigger\.href = authenticated/);
  assert.match(common, /Routes\.buildUrl\('\/profile'\)/);
  assert.match(common, /Routes\.buildUrl\('\/login'\).*\?return=/s);
});

test('auth-page account links never nest login or register routes inside return', () => {
  const common = read('dist/js/common.js');
  const siteHeader = read('packages/ui/src/layout/site-header.tsx');
  const authForm = read('apps/web/components/auth/auth-form.tsx');

  assert.match(common, /const isAuthPage = currentPath === '\/login' \|\| currentPath === '\/register'/);
  assert.match(common, /if \(currentPath === '\/login' \|\| currentPath === '\/register'\) return fallback/);
  assert.match(siteHeader, /const isAuthPage = currentPath === '\/login' \|\| currentPath === '\/register'/);
  assert.match(siteHeader, /new URLSearchParams\(window\.location\.search\)\.get\('return'\)/);
  assert.match(authForm, /typeof value !== 'string'/);
  assert.match(authForm, /stripLocalePrefix\(target\.pathname\)/);
  assert.match(authForm, /currentPath === '\/login' \|\| currentPath === '\/register'/);
});

test('static auth pages use extensionless canonical URLs and preserve redirect queries', () => {
  const nginx = read('infra/nginx/default.conf');
  const login = read('dist/login.html');
  const register = read('dist/register.html');

  assert.match(nginx, /location = \/login \{\n        try_files \/login\.html =404;\n    \}/);
  assert.match(nginx, /location = \/register \{\n        try_files \/register\.html =404;\n    \}/);
  assert.match(nginx, /location = \/login\.html \{\n        return 301 \/login\$is_args\$args;\n    \}/);
  assert.match(nginx, /location = \/register\.html \{\n        return 301 \/register\$is_args\$args;\n    \}/);
  assert.match(nginx, /location = \/login\/ \{\n        return 301 \/login\$is_args\$args;\n    \}/);
  assert.match(nginx, /location = \/register\/ \{\n        return 301 \/register\$is_args\$args;\n    \}/);
  assert.match(login, /<link rel="canonical" href="\/login">/);
  assert.match(register, /<link rel="canonical" href="\/register">/);
});

test('static footer has a common CSS fallback without Tailwind utilities', () => {
  const css = read('dist/css/common.css');

  assert.match(css, /#footer-container > footer/);
  assert.match(css, /#footer-container \[data-footer-rights\]\s*\{[^}]*text-align: center/s);
});

test('static registration confirms the password and preserves the return route', () => {
  const common = read('dist/js/common.js');
  const auth = read('dist/js/auth.js');

  assert.match(common, /name="confirmPassword"/);
  assert.match(common, /auth\.passwordMismatch/);
  assert.match(common, /authLinkWithReturn/);
  assert.match(common, /safeReturnTo/);
  assert.match(auth, /auth\.safeReturnTo/);
  assert.match(auth, /auth\.safeReturnTo\(params\.get\('return'\), '\/profile'\)/);
  assert.match(auth, /Routes\?\.normalizePath/);
  assert.doesNotMatch(auth, /georank:site-settings-applied/);
  assert.match(common, /Routes\.normalizePath\(window\.location\.pathname\).*'\/login'/s);
});

test('Next auth routes use the shared interactive auth form', () => {
  const loginPage = read('apps/web/app/[locale]/login/page.tsx');
  const registerPage = read('apps/web/app/[locale]/register/page.tsx');
  const authForm = read('apps/web/components/auth/auth-form.tsx');

  assert.match(loginPage, /<AuthForm/);
  assert.match(registerPage, /<AuthForm/);
  assert.match(loginPage, /<SiteHeader/);
  assert.match(registerPage, /<SiteHeader/);
  assert.doesNotMatch(loginPage, /LegacyStaticPage/);
  assert.doesNotMatch(registerPage, /LegacyStaticPage/);
  assert.match(authForm, /confirmPassword/);
  assert.match(authForm, /getVerifiedSession/);
  assert.match(authForm, /new URL\(value, RETURN_ORIGIN\)/);
  assert.match(authForm, /target\.origin !== RETURN_ORIGIN/);
});

test('Next user center keeps API settings on the current device and hides account forms in disclosures', () => {
  const account = read('apps/web/components/profile/account-settings.tsx');
  const staticProfile = read('dist/js/profile.js');
  const header = read('packages/ui/src/layout/site-header.tsx');
  const api = read('packages/api-sdk/src/auth.ts');
  const byok = read('packages/api-sdk/src/byok.ts');

  assert.match(byok, /georank_byok_config_v1/);
  assert.match(account, /profile-account-summary/);
  assert.match(account, /profile-api-panel/);
  assert.match(account, /<details/);
  assert.match(account, /getMyUsage/);
  assert.match(account, /readByokConfig/);
  assert.match(account, /saveByokConfig/);
  assert.match(account, /updateStoredUser/);
  assert.doesNotMatch(account, /setSession/);
  assert.doesNotMatch(account, /setTimeout/);
  assert.doesNotMatch(staticProfile, /setTimeout/);
  assert.match(read('apps/web/app/[locale]/profile/page.tsx'), /<SiteHeader/);
  assert.match(header, /localizeHref\(locale, '\/profile'\)/);
  assert.match(header, /<LanguageSwitcher/);
  assert.match(api, /export async function getMyUsage/);
});

test('protected profile pages verify cached sessions before rendering account data', () => {
  const session = read('packages/auth/src/session.ts');
  const guard = read('apps/web/components/auth/session-guard.tsx');
  const staticProfile = read('dist/js/profile.js');
  const siteHeader = read('packages/ui/src/layout/site-header.tsx');

  assert.match(session, /export async function getVerifiedSession/);
  assert.match(session, /georank:auth-changed/);
  assert.match(guard, /getVerifiedSession/);
  assert.match(staticProfile, /await Auth\.fetchMe/);
  assert.match(staticProfile, /Auth\.clearSession/);
  assert.match(siteHeader, /addEventListener\('georank:auth-changed'/);
});

test('browser API Key configuration is shared with modern AI requests', () => {
  const index = read('packages/api-sdk/src/index.ts');
  const byok = read('packages/api-sdk/src/byok.ts');
  const keywords = read('packages/api-sdk/src/keywords.ts');
  const solutions = read('packages/api-sdk/src/solutions.ts');
  const staticProfile = read('dist/js/profile.js');

  assert.match(index, /export \* from '\.\/byok'/);
  assert.match(byok, /export function getByokHeaders/);
  assert.match(byok, /X-GEOrank-BYOK-Key/);
  assert.match(keywords, /getByokHeaders/);
  assert.match(solutions, /getByokHeaders/);
  assert.match(staticProfile, /profile\.apiRequired/);
  assert.match(staticProfile, /profile\.apiInvalidBaseUrl/);
});

test('logout and account switching clear the previous browser API Key', () => {
  const session = read('packages/auth/src/session.ts');

  assert.match(session, /clearByokConfig/);
  assert.match(session, /existingUser\.id !== user\.id/);
  assert.match(session, /export function clearSession\(\)[\s\S]*clearByokConfig\(\)/);
});
