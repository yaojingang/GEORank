import {LegacyStaticPage, getLegacyMetadata} from '../../../_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('solutions');

export default function SolutionConversationPage() {
  return <LegacyStaticPage page="solutions" />;
}
