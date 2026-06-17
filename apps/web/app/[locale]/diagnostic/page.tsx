import {LegacyStaticPage, getLegacyMetadata} from '../_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('diagnostic');

export default function DiagnosticPage() {
  return <LegacyStaticPage page="diagnostic" />;
}
