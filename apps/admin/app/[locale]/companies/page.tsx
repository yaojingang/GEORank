'use client';

import {AdminSessionGuard} from '../../../components/auth/admin-session-guard';
import {AdminCompanies} from '../../../components/companies/admin-companies';

export default function AdminCompaniesPage() {
  return (
    <AdminSessionGuard>
      {({token}) => <AdminCompanies token={token} />}
    </AdminSessionGuard>
  );
}
