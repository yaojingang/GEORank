'use client';

import {AdminSessionGuard} from '../../../components/auth/admin-session-guard';
import {AdminUsers} from '../../../components/users/admin-users';

export default function AdminUsersPage() {
  return <AdminSessionGuard>{({token}) => <AdminUsers token={token} />}</AdminSessionGuard>;
}
