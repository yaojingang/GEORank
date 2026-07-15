import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./i18n/request.ts');

export default withNextIntl({
  reactStrictMode: true,
  devIndicators: false,
  transpilePackages: ['@georank/ui', '@georank/i18n', '@georank/api-sdk', '@georank/auth']
});
