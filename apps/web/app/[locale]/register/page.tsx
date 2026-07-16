import type {Metadata} from 'next';
import {getTranslations} from 'next-intl/server';
import {SiteHeader} from '@georank/ui';

import {AuthForm} from '../../../components/auth/auth-form';

export async function generateMetadata({params}: {params: Promise<{locale: string}>}): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations({locale, namespace: 'web.metadata'});
  return {title: t('registerTitle'), description: t('registerDescription')};
}

export default async function RegisterPage({
  params,
  searchParams
}: {
  params: Promise<{locale: string}>;
  searchParams: Promise<{return?: string}>;
}) {
  const [{locale}, query] = await Promise.all([params, searchParams]);
  return (
    <>
      <SiteHeader locale={locale} />
      <AuthForm locale={locale} mode="register" returnTo={query.return} />
    </>
  );
}
