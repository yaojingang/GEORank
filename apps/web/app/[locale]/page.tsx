import {LegacyStaticPage, getLegacyMetadata} from './_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('index');

export default function HomePage() {
  return <LegacyStaticPage page="index" />;
}
