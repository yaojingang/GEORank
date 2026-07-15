'use client';

import {AdminSessionGuard} from '../../../components/auth/admin-session-guard';
import {AdminHomepage} from '../../../components/homepage/admin-homepage';

export default function AdminHomepagePage() {
  return (
    <AdminSessionGuard>
      {({token}) => <AdminHomepage token={token} />}
    </AdminSessionGuard>
  );
}
