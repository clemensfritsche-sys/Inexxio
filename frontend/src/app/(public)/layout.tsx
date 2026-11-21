import { PasskeyNudge } from '@/components/auth/passkey-nudge';

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <main className="min-h-screen">{children}</main>
      <PasskeyNudge />
    </>
  );
}
