import createMiddleware from 'next-intl/middleware';
import {defaultLocale, locales} from './routing';

export const middleware = createMiddleware({
  locales,
  defaultLocale,
  localePrefix: 'as-needed'
});
