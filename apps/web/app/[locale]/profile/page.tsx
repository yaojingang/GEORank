import type {Metadata} from 'next';
import {getTranslations} from 'next-intl/server';
import {SiteHeader} from '@georank/ui';

import {AccountSettings} from '../../../components/profile/account-settings';

export async function generateMetadata({params}: {params: Promise<{locale: string}>}): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations({locale, namespace: 'web.metadata'});
  return {title: t('profileTitle'), description: t('profileDescription')};
}

export default async function ProfilePage({params}: {params: Promise<{locale: string}>}) {
  const {locale} = await params;
  return (
    <>
      <SiteHeader locale={locale} />
      <AccountSettings locale={locale} />
    </>
  );
}
