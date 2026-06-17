'use client';

import {AdminSessionGuard} from '../../components/auth/admin-session-guard';
import {AdminDashboard} from '../../components/dashboard/admin-dashboard';

export default function AdminDashboardPage() {
  return (
    <AdminSessionGuard>
      {({token, userLabel}) => <AdminDashboard token={token} userLabel={userLabel} />}
    </AdminSessionGuard>
  );
}
