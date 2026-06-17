import {LegacyStaticPage, getLegacyMetadata} from '../_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('company-submit');

export default function CompanySubmitPage() {
  return <LegacyStaticPage page="company-submit" />;
}
