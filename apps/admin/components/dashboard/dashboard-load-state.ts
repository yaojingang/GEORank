import type {AdminDashboardResponse, AdminRecentFailuresResponse} from '@georank/api-sdk';

export type DashboardLoadState = {
  dashboard: AdminDashboardResponse | null;
  failures: AdminRecentFailuresResponse | null;
  error: string;
  loading: boolean;
};

export function mergeDashboardLoadResults(
  current: DashboardLoadState,
  dashboardResult: PromiseSettledResult<AdminDashboardResponse>,
  failuresResult: PromiseSettledResult<AdminRecentFailuresResponse>,
  fallbackError: string
): DashboardLoadState {
  const errors: string[] = [];
  if (dashboardResult.status === 'rejected') {
    errors.push(
      dashboardResult.reason instanceof Error ? dashboardResult.reason.message : fallbackError
    );
  }
  if (failuresResult.status === 'rejected') {
    errors.push(
      failuresResult.reason instanceof Error ? failuresResult.reason.message : fallbackError
    );
  }
  return {
    dashboard: dashboardResult.status === 'fulfilled' ? dashboardResult.value : current.dashboard,
    failures: failuresResult.status === 'fulfilled' ? failuresResult.value : current.failures,
    error: errors.join(' · '),
    loading: false
  };
}
