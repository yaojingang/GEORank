'use client';

import {AdminSessionGuard} from '../../../components/auth/admin-session-guard';
import {AdminKeywords} from '../../../components/keywords/admin-keywords';

export default function AdminKeywordsPage() {
  return (
    <AdminSessionGuard>
      {({token}) => <AdminKeywords token={token} />}
    </AdminSessionGuard>
  );
}
