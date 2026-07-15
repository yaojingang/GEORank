import type {Metadata} from 'next';

import {AccountSettings} from '../../../components/profile/account-settings';

export const metadata: Metadata = {
  title: 'Account center | GEOrank',
  description: 'Manage account profile and password settings.'
};

export default async function ProfilePage({params}: {params: Promise<{locale: string}>}) {
  const {locale} = await params;
  return <AccountSettings locale={locale} />;
}
