import {getRequestConfig} from 'next-intl/server';
import {defaultLocale, locales} from './routing';

export default getRequestConfig(async ({requestLocale}) => {
  const resolvedLocale = await requestLocale;
  const locale: string =
    resolvedLocale && locales.includes(resolvedLocale as (typeof locales)[number])
      ? resolvedLocale
      : defaultLocale;
  const messages = (await import(`./dictionaries/${locale}.ts`)).default;
  return {locale, messages};
});
