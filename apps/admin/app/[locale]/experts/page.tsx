'use client';

import {AdminSessionGuard} from '../../../components/auth/admin-session-guard';
import {AdminExperts} from '../../../components/experts/admin-experts';

export default function AdminExpertsPage() {
  return (
    <AdminSessionGuard>
      {({token}) => <AdminExperts token={token} />}
    </AdminSessionGuard>
  );
}
