import type { Metadata } from "next";
import LoginForm from "@/components/ui/LoginForm";

export const metadata: Metadata = {
  title: "Anmelden | Inexxio",
  robots: { index: false },
};

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-brand-700">Inexxio</h1>
          <p className="text-gray-500 text-sm mt-1">Enterprise Central System</p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
