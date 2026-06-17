import {LegacyStaticPage, getLegacyMetadata} from '../_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('register');

export default function RegisterPage() {
  return <LegacyStaticPage page="register" />;
}
