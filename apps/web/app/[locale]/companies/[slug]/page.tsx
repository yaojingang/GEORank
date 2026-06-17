import {LegacyStaticPage, getLegacyMetadata} from '../../_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('company');

export default function CompanyDetailPage() {
  return <LegacyStaticPage page="company" />;
}
