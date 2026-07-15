import {LegacyStaticPage, getLegacyMetadata} from '../_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('keywords');

export default function KeywordsPage() {
  return <LegacyStaticPage page="keywords" />;
}
