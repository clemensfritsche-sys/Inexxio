import { Navbar } from '@/components/layout/navbar';
import { Footer } from '@/components/layout/footer';
import { PasskeyNudge } from '@/components/auth/passkey-nudge';
import { FeedbackPin } from '@/components/feedback/feedback-pin';

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navbar />
      <main className="min-h-screen">{children}</main>
      <Footer />
      <PasskeyNudge />
      {/* Testnotizen: nur in der Testumgebung, für JEDE angemeldete Rolle. */}
      <FeedbackPin />
    </>
  );
}
