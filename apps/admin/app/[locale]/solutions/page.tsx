'use client';

import {AdminSessionGuard} from '../../../components/auth/admin-session-guard';
import {AdminSolutions} from '../../../components/solutions/admin-solutions';

export default function AdminSolutionsPage() {
  return (
    <AdminSessionGuard>
      {({token}) => <AdminSolutions token={token} />}
    </AdminSessionGuard>
  );
}
