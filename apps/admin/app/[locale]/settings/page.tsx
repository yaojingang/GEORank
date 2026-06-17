'use client';

import {AdminSessionGuard} from '../../../components/auth/admin-session-guard';
import {AdminSettings} from '../../../components/settings/admin-settings';

export default function AdminSettingsPage() {
  return <AdminSessionGuard>{({token}) => <AdminSettings token={token} />}</AdminSessionGuard>;
}
