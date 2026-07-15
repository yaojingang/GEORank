'use client';

import {AdminSessionGuard} from '../../../components/auth/admin-session-guard';
import {AdminDiagnostics} from '../../../components/diagnostics/admin-diagnostics';

export default function AdminDiagnosticsPage() {
  return (
    <AdminSessionGuard>
      {({token}) => <AdminDiagnostics token={token} />}
    </AdminSessionGuard>
  );
}
