import {LegacyStaticPage, getLegacyMetadata} from '../_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('tutorial');

export default function TutorialPage() {
  return <LegacyStaticPage page="tutorial" />;
}
