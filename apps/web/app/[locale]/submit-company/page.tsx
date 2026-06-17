import {LegacyStaticPage, getLegacyMetadata} from '../_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('company-submit');

export default function SubmitCompanyPage() {
  return <LegacyStaticPage page="company-submit" />;
}
