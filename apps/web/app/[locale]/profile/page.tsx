import {LegacyStaticPage, getLegacyMetadata} from '../_legacy-page';

export const metadata = getLegacyMetadata('profile');

export default function ProfilePage() {
  return <LegacyStaticPage page="profile" />;
}
