import {LegacyStaticPage, getLegacyMetadata} from '../_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('tools');

export default function ToolsPage() {
  return <LegacyStaticPage page="tools" />;
}
