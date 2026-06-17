'use client';

import {AdminSessionGuard} from '../../../components/auth/admin-session-guard';
import {AdminTutorials} from '../../../components/tutorials/admin-tutorials';

export default function AdminTutorialsPage() {
  return <AdminSessionGuard>{({token}) => <AdminTutorials token={token} />}</AdminSessionGuard>;
}
