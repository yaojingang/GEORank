import {readFile} from 'node:fs/promises';
import {mergeDashboardLoadResults} from '../apps/admin/components/dashboard/dashboard-load-state.ts';

const files = [
  'apps/admin/components/settings/admin-settings.tsx',
  'apps/admin/components/users/admin-users.tsx',
  'apps/admin/components/dashboard/admin-dashboard.tsx'
];

const failures = [];
for (const file of files) {
  const source = await readFile(new URL(`../${file}`, import.meta.url), 'utf8');
  if (source.includes('Promise.all(')) {
    failures.push(`${file}: fail-fast Promise.all remains`);
  }
  if (!source.includes('Promise.allSettled(')) {
    failures.push(`${file}: missing independent Promise.allSettled loading`);
  }
}

if (failures.length > 0) {
  console.error(failures.join('\n'));
  process.exit(1);
}

const originalDashboard = {total_companies: 1};
const originalFailures = {companies: [], diagnostics: []};
const retryState = mergeDashboardLoadResults(
  {dashboard: originalDashboard, failures: originalFailures, error: '', loading: false},
  {status: 'rejected', reason: new Error('dashboard unavailable')},
  {status: 'fulfilled', value: {companies: [{id: 'fresh'}], diagnostics: []}},
  'load failed'
);
if (retryState.dashboard !== originalDashboard) {
  throw new Error('Dashboard retry discarded previously loaded dashboard data.');
}
if (retryState.failures === originalFailures) {
  throw new Error('Dashboard retry did not apply the newly fulfilled failures section.');
}

console.log('Admin settings, users, and dashboard loaders preserve partial results.');
