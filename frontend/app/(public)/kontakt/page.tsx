import type { Metadata } from "next";
import ContactForm from "@/components/ui/ContactForm";

export const metadata: Metadata = {
  title: "Kontakt",
  description: "Nehmen Sie Kontakt mit Inexxio auf.",
};

export default function KontaktPage() {
  return (
    <div className="max-w-2xl mx-auto px-4 py-16">
      <h1 className="text-3xl font-bold text-gray-900 mb-4">Kontakt</h1>
      <p className="text-gray-600 mb-10">
        Wir freuen uns auf Ihre Nachricht. Wir antworten in der Regel innerhalb
        von 1–2 Werktagen.
      </p>
      <ContactForm />
    </div>
  );
}
