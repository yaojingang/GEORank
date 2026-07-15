import {Buffer} from 'node:buffer';

const sensitiveKeyPattern = /(?:^|_)(?:address|contact|email|fax|mobile|phone|qq|tel|telephone|wechat|weixin|wxid)(?:_|$)/i;
const sensitiveChineseKeyPattern = /(?:电子邮箱|微信(?:账号|号)?|联系电话|联系地址|手机(?:号|号码)?|电话号码|座机|传真|家庭住址|住址|家庭地址|居住地址|通讯地址|收件地址|详细地址)/;
const legacyOwner = ['AI', 'haoke'].join('').toLowerCase();
const legacyRepository = 'GEORank'.toLowerCase();
const publicBinaryExtensions = new Set([
  '.gif', '.ico', '.jpeg', '.jpg', '.otf', '.png', '.ttf', '.webp', '.woff', '.woff2',
]);
const namedHtmlEntities = new Map([
  ['amp', '&'],
  ['colon', ':'],
  ['commat', '@'],
  ['hyphen', '-'],
  ['lpar', '('],
  ['period', '.'],
  ['rpar', ')'],
  ['sol', '/'],
]);
const boundedEmailPattern = /[\p{L}\p{N}._%+-]{1,64}\s*@\s*[\p{L}\p{N}-]{1,63}(?:\s*\.\s*[\p{L}\p{N}-]{1,63}){1,5}(?![\p{L}\p{N}-])/iu;
const phonePatternKinds = new Set([
  'contextual-phone', 'grouped-phone', 'international-phone', 'landline-phone',
  'mobile-phone', 'telephone-uri',
]);

const sensitiveTextPatterns = [
  ['email-uri', /\bmailto\s*:/i],
  [
    'email-account',
    /电子邮箱\s*(?:账号|帐号|地址|号码|联系方式)\s*[:：]\s*\S{3,}/,
  ],
  ['telephone-uri', /\btel\s*:/i],
  ['wechat-uri', /\b(?:wechat|weixin)\s*:\s*[@a-z0-9_-]{5,}/i],
  ['wechat-id', /\bwxid[_:-]?[a-z0-9_-]{5,}\b/i],
  [
    'wechat-account',
    /(?:微信|wechat|weixin)\s*(?:号|账号|帐号|账户|ID|id|联系方式|联系)\s*[:：]?\s*[@a-z0-9_-]{5,}/i,
  ],
  ['mobile-phone', /(?<!\d)(?:86)?1[3-9](?:[ ().\/-]?\d){9}(?!\d)/],
  ['landline-phone', /(?<!\d)(?:\(0\d{2,3}\)|0\d{2,3})[ ().\/-]?\d{7,8}(?!\d)/],
  ['international-phone', /(?<![\d.])\+\s*\d{1,3}(?:[ ().\/-]?\d){7,14}(?!\d)/],
  [
    'grouped-phone',
    /(?<![\d.])(?:\(\d{2,4}\)|\d{2,4})[ .\/-](?:\d{2,4}[ .\/-]){1,3}\d{3,4}(?!\d)/,
  ],
  [
    'contextual-phone',
    /(?:telephone|mobile|cell(?:phone)?|fax|phone|电话|手机(?:号)?|座机|传真|联系号码|联系电话|联系方式)\s*[:：]?\s*(?:\+\s*)?(?:\(\s*\d{1,4}\s*\)|\d{2,4})(?:[ ().\/-]?\d){5,12}/i,
  ],
  ['home-address', /home\s+address\s*[:：]\s*\d{1,8}\s+[a-z0-9 .'-]{3,80}/i],
];

function decodeHtmlEntities(value) {
  return value.replace(
    /&(?:#(\d{1,7});?|#x([0-9a-f]{1,6});?|([a-z][a-z0-9]+);)/gi,
    (entity, decimal, hexadecimal, named) => {
      if (named) return namedHtmlEntities.get(named.toLowerCase()) ?? entity;
      const codePoint = Number.parseInt(decimal ?? hexadecimal, decimal ? 10 : 16);
      if (!Number.isInteger(codePoint) || codePoint < 1 || codePoint > 0x10FFFF) return entity;
      if (codePoint >= 0xD800 && codePoint <= 0xDFFF) return entity;
      return String.fromCodePoint(codePoint);
    },
  );
}

export function normalizePublicText(value) {
  const compatibilityNormalized = String(value).normalize('NFKC');
  return decodeHtmlEntities(compatibilityNormalized)
    .normalize('NFKC')
    .replace(/\p{Cf}/gu, '')
    .replace(/(?<=\d)[_·•](?=\d)/g, '-')
    .normalize('NFKC')
    .replace(/[\u2010-\u2015\u2212\uFE58\uFE63]/g, '-')
    .replace(/[\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000\s]+/g, ' ')
    .replace(/\s*([():：-])\s*/g, '$1')
    .replaceAll('：', ':')
    .trim();
}

function findEmail(text) {
  let searchFrom = 0;
  while (searchFrom < text.length) {
    const at = text.indexOf('@', searchFrom);
    if (at === -1) return null;
    searchFrom = at + 1;
    if (at >= 3 && text.slice(at - 3, at + 12).toLowerCase() === 'git@github.com:') continue;
    const windowStart = Math.max(0, at - 80);
    const match = text.slice(windowStart, Math.min(text.length, at + 330)).match(boundedEmailPattern);
    if (match && windowStart + match.index <= at && windowStart + match.index + match[0].length > at) {
      return match[0];
    }
  }
  return null;
}

function maskPhoneSafeContexts(text) {
  return text.replace(
    /\b(?:(?:https?:\/\/(?:dx\.)?doi\.org\/)|(?:doi\s*:\s*))?10\.\d{4,9}\/[-._;()/:a-z0-9]+/gi,
    (match) => ' '.repeat(match.length),
  );
}

function findChineseAddress(text) {
  const contexts = [
    /(?:家庭住址|住址|家庭地址|居住地址|详细地址|联系地址|通讯地址|收件地址)\s*(?::|为|是|位于|在)\s*([^\n,，;；]{6,100})/g,
    /(?<!网络)(?<!项目)(?<!仓库)(?<!网站)(?<!网址)(?<!注册)(?<!IP)(?<!ip)地址\s*(?::|为|是|位于|在)\s*([^\n,，;；]{6,100})/g,
  ];
  for (const context of contexts) {
    for (const match of text.matchAll(context)) {
      const candidate = match[1];
      const hasDeliveryShape = /(?:路|街|巷|弄|道|号|室|楼|栋|单元|村)/.test(candidate);
      const hasNumberedDestination = /(?:\d{1,8}|[〇零一二三四五六七八九十百]{1,8})\s*(?:号|室|楼|栋|单元)?/.test(candidate);
      if (hasDeliveryShape && hasNumberedDestination) return match[0];
    }
  }
  return null;
}

function normalizeKey(key) {
  return normalizePublicText(key)
    .replace(/([\p{Ll}\p{N}])(\p{Lu})/gu, '$1_$2')
    .replace(/[^\p{L}\p{N}]+/gu, '_')
    .toLowerCase();
}

function inspectText(value, path, violations) {
  const normalized = normalizePublicText(value);
  const phoneScanText = maskPhoneSafeContexts(normalized);
  const email = findEmail(normalized);
  if (email) violations.push({kind: 'email', path, match: email});
  const chineseAddress = findChineseAddress(normalized);
  if (chineseAddress) violations.push({kind: 'address', path, match: chineseAddress});
  for (const [kind, pattern] of sensitiveTextPatterns) {
    const match = (phonePatternKinds.has(kind) ? phoneScanText : normalized).match(pattern);
    if (match) violations.push({kind, path, match: match[0]});
  }
}

function inspectValue(value, path, violations) {
  if (typeof value === 'string') {
    inspectText(value, path, violations);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => inspectValue(item, `${path}[${index}]`, violations));
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const [key, item] of Object.entries(value)) {
    const childPath = `${path}.${key}`;
    const normalizedKey = normalizeKey(key);
    if (sensitiveKeyPattern.test(normalizedKey) || sensitiveChineseKeyPattern.test(normalizedKey)) {
      violations.push({kind: 'sensitive-key', path: childPath, match: key});
    }
    inspectValue(item, childPath, violations);
  }
}

export function findSensitivePublicData(value) {
  const violations = [];
  inspectValue(value, '$', violations);
  return violations;
}

export function hasLegacyRepositoryReference(value) {
  const normalized = normalizePublicText(value).toLowerCase();
  return normalized.includes(`${legacyOwner}/${legacyRepository}`);
}

function decodeUtf16BigEndian(buffer) {
  const swapped = Buffer.allocUnsafe(buffer.length - (buffer.length % 2));
  for (let index = 0; index < swapped.length; index += 2) {
    swapped[index] = buffer[index + 1];
    swapped[index + 1] = buffer[index];
  }
  return swapped.toString('utf16le');
}

export function decodeTextBufferCandidates(value) {
  const buffer = Buffer.isBuffer(value) ? value : Buffer.from(value);
  const candidates = new Set([buffer.toString('utf8')]);
  if (buffer.includes(0) || buffer[0] === 0xFE || buffer[0] === 0xFF) {
    candidates.add(buffer.toString('utf16le'));
    candidates.add(decodeUtf16BigEndian(buffer));
  }
  return [...candidates];
}

export function hasLegacyRepositoryReferenceInBuffer(value) {
  const buffer = Buffer.isBuffer(value) ? value : Buffer.from(value);
  return [buffer.toString('utf8'), buffer.toString('utf16le'), decodeUtf16BigEndian(buffer)]
    .some((decoded) => hasLegacyRepositoryReference(decoded));
}

export function isPublicContentPath(path) {
  const normalized = String(path).replaceAll('\\', '/').toLowerCase();
  return [
    'assets/public/',
    'data/public/',
    'public/assets/',
    'public/data/',
    'runtime/homepages/public/',
  ].some((prefix) => normalized.startsWith(prefix))
    || /^runtime\/homepages\/releases\/[^/]+\/(?:manifest\.json|source\/)/.test(normalized);
}

export function isPublicTextPath(path) {
  if (!isPublicContentPath(path)) return false;
  return !isKnownBinaryPath(path);
}

export function isKnownBinaryPath(path) {
  const normalized = String(path).replaceAll('\\', '/').toLowerCase();
  const name = normalized.slice(normalized.lastIndexOf('/') + 1);
  const extension = name.includes('.') ? name.slice(name.lastIndexOf('.')) : '';
  return publicBinaryExtensions.has(extension);
}
