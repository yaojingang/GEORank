import assert from 'node:assert/strict';
import {Buffer} from 'node:buffer';
import {performance} from 'node:perf_hooks';
import test from 'node:test';

import {
  findSensitivePublicData,
  hasLegacyRepositoryReference,
  hasLegacyRepositoryReferenceInBuffer,
  normalizePublicText,
} from './public-content-policy.mjs';

test('normalizes Unicode compatibility characters and phone separators', () => {
  assert.equal(
    normalizePublicText('Ｔｅｌｅｐｈｏｎｅ：\u3000（０１０）‐１２３４‑５６７８'),
    'Telephone:(010)-1234-5678',
  );
});

test('detects sensitive contact mutations after normalization', () => {
  const rejected = [
    '138 0013 8000',
    '138-0013-8000',
    '138.0013.8000',
    '138/0013/8000',
    '138_0013_8000',
    '138·0013·8000',
    '138•0013•8000',
    '138\u200B0013\u200B8000',
    '010-12345678',
    '(010)12345678',
    'telephone: 010 1234 5678',
    '021-61234567',
    'mobile（+86）138-0013-8000',
    'fax: +1 (415) 555-2671',
    '415-555-2671',
    '44 20 7946 0958',
    'email: person@example.com',
    'person@\u200Bexample.com',
    '电子邮箱账号：张三＠例子．公司',
    '电子邮箱账号：zhangsan',
    'mailto:person@example.com',
    'person&#64;example&#46;com',
    'person&#64example&#46com',
    'mailto&#58;person&commat;example&period;com',
    'wxid_example_2026',
    '微信账号：example_2026',
    '微信号：example_2026',
    '微信号&#58;example_2026',
    'wechat id: example_2026',
    'wechat:example_2026',
    'weixin:example_2026',
    '地址: 北京市朝阳区建国路88号',
    '家庭住址为上海市浦东新区世纪大道100号',
    '联系地址位于广东省深圳市南山区科苑路15号',
    '地址是浙江省杭州市西湖区文三路90号',
    '住址为北京市朝阳区建国路88号',
    '家庭地址在上海市浦东新区世纪大道100号',
    '居住地址为广东省深圳市南山区科苑路15号',
    '地址：香港九龙尖沙咀弥敦道100号',
    '住址为北京市朝阳区建国路八十八号',
    'https://example.com/?phone=021-61234567',
    'https://wa.me/8613800138000',
    'https://example.com/contact/13800138000',
  ];

  for (const value of rejected) {
    assert.notDeepEqual(findSensitivePublicData(value), [], value);
  }
});

test('allows non-contact discussion of channels and research', () => {
  const allowed = [
    '长期运营微信公众号并公开分享',
    '电子邮箱安全研究',
    '研究 telephone routing 与 mobile web 体验',
    'git@github.com:yaojingang/GEORank.git',
    'https://doi.org/10.1234/5678',
    'doi:10.1234/5678',
    '10.1234/5678',
    '研究网络地址解析策略',
    '项目地址是公开仓库首页',
    '网络地址是市区道路设计规范',
    '项目地址是北京市交通路网数据集',
    '长期维护注册地址治理规范',
    '2010 年创办平台，累计服务 500 强企业',
  ];

  for (const value of allowed) {
    assert.deepEqual(findSensitivePublicData(value), [], value);
  }
});

test('detects sensitive keys throughout structured public data', () => {
  const violations = findSensitivePublicData({
    profile: {
      contact_phone: 'redacted',
      contactPhone: 'redacted',
      'contact-phone': 'redacted',
      emailAddress: 'redacted',
      手机号: '138_0013_8000',
      电话号码: '138·0013·8000',
      家庭住址: 'redacted',
      住址: '北京市朝阳区建国路88号',
      家庭地址: '上海市浦东新区世纪大道100号',
      居住地址: '广东省深圳市南山区科苑路15号',
      通讯地址: '浙江省杭州市西湖区文三路90号',
      收件地址: '香港九龙尖沙咀弥敦道100号',
    },
  });
  assert.equal(violations.some(({kind, path}) => kind === 'sensitive-key' && path === '$.profile.contact_phone'), true);
  assert.equal(violations.some(({kind, path}) => kind === 'sensitive-key' && path === '$.profile.contactPhone'), true);
  assert.equal(violations.some(({kind, path}) => kind === 'sensitive-key' && path === '$.profile.contact-phone'), true);
  assert.equal(violations.some(({kind, path}) => kind === 'sensitive-key' && path === '$.profile.emailAddress'), true);
  assert.equal(violations.some(({kind, path}) => kind === 'sensitive-key' && path === '$.profile.手机号'), true);
  assert.equal(violations.some(({kind, path}) => kind === 'sensitive-key' && path === '$.profile.电话号码'), true);
  assert.equal(violations.some(({kind, path}) => kind === 'sensitive-key' && path === '$.profile.家庭住址'), true);
  for (const key of ['住址', '家庭地址', '居住地址', '通讯地址', '收件地址']) {
    assert.equal(
      violations.some(({kind, path}) => kind === 'sensitive-key' && path === `$.profile.${key}`),
      true,
      key,
    );
  }
});

test('bounds email scanning time for long invalid candidates', () => {
  const adversarial = `${'a'.repeat(16_000)}@${'b'.repeat(16_000)}`;
  const started = performance.now();
  assert.deepEqual(findSensitivePublicData(adversarial), []);
  assert.ok(performance.now() - started < 250, 'email scan exceeded the 250ms regression budget');
});

test('recognizes legacy repository URL variants without path exceptions', () => {
  const owner = ['AI', 'haoke'].join('');
  const repository = 'GEORank';
  for (const value of [
    `https://github.com/${owner}/${repository}`,
    `https://github.com/${owner.toUpperCase()}/${repository.toLowerCase()}.git`,
    `git@github.com:${owner}/${repository}.git`,
    `ssh://git@github.com/${owner}/${repository}.git`,
    `https://github.com/${owner}&#47;${repository}`,
    `https://github.com/${owner}&#47${repository}`,
    `https://github.com/${owner}&#x2f${repository}`,
  ]) {
    assert.equal(hasLegacyRepositoryReference(value), true, value);
  }
  assert.equal(hasLegacyRepositoryReference('https://github.com/yaojingang/GEORank'), false);
});

test('recognizes legacy owner text in UTF-16 buffers', () => {
  const owner = ['AI', 'haoke'].join('');
  const reference = `https://github.com/${owner}/GEORank.git`;
  const littleEndian = Buffer.from(reference, 'utf16le');
  const bigEndian = Buffer.from(littleEndian);
  for (let index = 0; index + 1 < bigEndian.length; index += 2) {
    [bigEndian[index], bigEndian[index + 1]] = [bigEndian[index + 1], bigEndian[index]];
  }
  assert.equal(hasLegacyRepositoryReferenceInBuffer(littleEndian), true);
  assert.equal(hasLegacyRepositoryReferenceInBuffer(bigEndian), true);
});
