import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Anmelden | Inexxio AG',
  robots: { index: false, follow: false },
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#f0ebe3' }}>
      <div className="flex-1">
        {children}
      </div>
    </div>
  );
}
