import type {ReactNode} from 'react';

export function AdminShell({
  sidebar,
  children
}: {
  sidebar: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="admin-shell">
      {sidebar}
      <div className="admin-shell__content">{children}</div>
    </div>
  );
}
