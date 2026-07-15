import {LegacyStaticPage, getLegacyMetadata} from '../_legacy-page';

export const dynamic = 'force-dynamic';
export const metadata = getLegacyMetadata('plans');

export default function PlansPage() {
  return <LegacyStaticPage page="plans" />;
}
