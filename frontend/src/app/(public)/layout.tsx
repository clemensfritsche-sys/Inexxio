import { PasskeyNudge } from '@/components/auth/passkey-nudge';
import { FeedbackPin } from '@/components/feedback/feedback-pin';

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <main className="min-h-screen">{children}</main>
      <PasskeyNudge />
      {/* Testnotizen: nur in der Testumgebung, für JEDE angemeldete Rolle. */}
      <FeedbackPin />
    </>
  );
}
