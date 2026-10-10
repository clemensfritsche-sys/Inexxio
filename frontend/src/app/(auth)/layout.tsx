import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Anmelden | INEXXIO AG',
  robots: { index: false, follow: false },
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-2)' }}>
      <div className="flex-1">
        {children}
      </div>
    </div>
  );
}
