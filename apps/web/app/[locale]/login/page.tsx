import {LegacyStaticPage, getLegacyMetadata} from '../_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('login');

export default function LoginPage() {
  return <LegacyStaticPage page="login" />;
}
