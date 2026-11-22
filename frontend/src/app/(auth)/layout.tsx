import type { Metadata } from 'next';
import { ShellLanguage } from '@/components/layout/site-shell';

export const metadata: Metadata = {
  title: 'Anmelden',
  robots: { index: false, follow: false },
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-2)' }}>
      {/* Die Anmeldung spricht die Sprache der Seite, von der man kommt. */}
      <ShellLanguage />
      <div className="flex-1">
        {children}
      </div>
    </div>
  );
}
