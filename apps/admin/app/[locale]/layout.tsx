import type {ReactNode} from 'react';

import '../globals.css';
import {NextIntlClientProvider} from 'next-intl';
import {getMessages} from 'next-intl/server';
import {AdminShell, AdminSidebar} from '@georank/ui';

export default async function AdminLayout({
  children,
  params
}: {
  children: ReactNode;
  params: Promise<{locale: string}>;
}) {
  const {locale} = await params;
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider messages={messages}>
          <AdminShell sidebar={<AdminSidebar locale={locale} />}>{children}</AdminShell>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
