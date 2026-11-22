import { AccountFrame } from '@/components/account/account-frame';
import { ShellLanguage } from '@/components/layout/site-shell';

/** Das Konto – in der Sprache der Seite, von der man kommt (`ShellLanguage`). */
export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <ShellLanguage />
      <AccountFrame>{children}</AccountFrame>
    </>
  );
}
