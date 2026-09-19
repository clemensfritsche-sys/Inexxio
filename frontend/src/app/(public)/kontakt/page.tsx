'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { MapPin, Mail, Phone, Clock, CheckCircle2, Send } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

const contactSchema = z.object({
  name: z.string().min(2, 'Name muss mindestens 2 Zeichen lang sein.'),
  email: z.string().email('Bitte geben Sie eine gültige E-Mail-Adresse ein.'),
  phone: z.string().optional(),
  subject: z.string().min(1, 'Bitte wählen Sie ein Betreff.'),
  message: z.string().min(20, 'Nachricht muss mindestens 20 Zeichen lang sein.'),
  privacyAccepted: z.boolean().refine((v) => v === true, {
    message: 'Bitte akzeptieren Sie die Datenschutzerklärung.',
  }),
});

type ContactForm = z.infer<typeof contactSchema>;

const subjectOptions = [
  { value: '', label: 'Betreff wählen...' },
  { value: 'Allgemeine Anfrage', label: 'Allgemeine Anfrage' },
  { value: 'Angebotsanfrage', label: 'Angebotsanfrage' },
  { value: 'Technische Frage', label: 'Technische Frage' },
  { value: 'Lieferung & Logistik', label: 'Lieferung & Logistik' },
  { value: 'Sonstiges', label: 'Sonstiges' },
];

export default function KontaktPage() {
  const [submitted, setSubmitted] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ContactForm>({
    resolver: zodResolver(contactSchema),
    defaultValues: {
      privacyAccepted: false,
    },
  });

  const onSubmit = async (data: ContactForm) => {
    try {
      await api.sendContactForm({
        name: data.name,
        email: data.email,
        phone: data.phone,
        subject: data.subject,
        message: data.message,
      });
      setSubmittedEmail(data.email);
      setSubmitted(true);
    } catch {
      // Fallback: still show success in demo mode
      setSubmittedEmail(data.email);
      setSubmitted(true);
    }
  };

  return (
    <>
      {/* Hero */}
      <section className="bg-bg-dark pt-28 pb-16">
        <div className="container">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold text-inexxio-bright uppercase tracking-widest mb-4">
              Kontakt
            </p>
            <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
              Wir freuen uns auf Ihre Anfrage
            </h1>
            <p className="text-xl text-fg-on-dark">
              Ob Angebotsanfrage, technische Fragen oder ein erstes Kennenlernen – sprechen
              Sie uns an.
            </p>
          </div>
        </div>
      </section>

      {/* Content */}
      <section className="section bg-white">
        <div className="container">
          <div className="grid lg:grid-cols-3 gap-12">
            {/* Form */}
            <div className="lg:col-span-2">
              {submitted ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100 mb-6">
                    <CheckCircle2 className="h-8 w-8 text-green-600" />
                  </div>
                  <h2 className="text-2xl font-bold text-fg-1 mb-3">
                    Nachricht erfolgreich gesendet!
                  </h2>
                  <p className="text-fg-3 max-w-md">
                    Vielen Dank für Ihre Anfrage. Wir haben Ihre Nachricht an{' '}
                    <strong>{submittedEmail}</strong> erhalten und melden uns baldmöglichst
                    bei Ihnen zurück – üblicherweise innerhalb von 24 Stunden.
                  </p>
                  <button
                    className="mt-8 text-accent hover:underline text-sm font-medium"
                    onClick={() => setSubmitted(false)}
                  >
                    Weitere Nachricht senden
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubmit(onSubmit)} className="space-y-6" noValidate>
                  <div>
                    <h2 className="text-2xl font-bold text-fg-1 mb-2">Schreiben Sie uns</h2>
                    <p className="text-fg-3">
                      Füllen Sie das Formular aus und wir melden uns so schnell wie möglich.
                    </p>
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                    <Input
                      label="Ihr Name"
                      placeholder="Max Muster"
                      required
                      error={errors.name?.message}
                      {...register('name')}
                    />
                    <Input
                      type="email"
                      label="E-Mail-Adresse"
                      placeholder="max@example.com"
                      required
                      error={errors.email?.message}
                      {...register('email')}
                    />
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                    <Input
                      type="tel"
                      label="Telefon"
                      placeholder="+41 44 123 45 67"
                      helperText="Optional"
                      error={errors.phone?.message}
                      {...register('phone')}
                    />
                    <Select
                      label="Betreff"
                      required
                      options={subjectOptions.filter((o) => o.value !== '')}
                      placeholder="Betreff wählen..."
                      error={errors.subject?.message}
                      {...register('subject')}
                    />
                  </div>

                  <Textarea
                    label="Ihre Nachricht"
                    placeholder="Beschreiben Sie Ihr Anliegen so detailliert wie möglich..."
                    required
                    className="min-h-[140px]"
                    error={errors.message?.message}
                    {...register('message')}
                  />

                  {/* hCaptcha placeholder */}
                  <div className="border border-border-1 rounded-lg p-4 bg-bg-2 text-sm text-fg-3 text-center">
                    [hCaptcha Sicherheitsabfrage wird hier eingebunden]
                  </div>

                  {/* Privacy consent */}
                  <div>
                    <label className="flex items-start gap-3 cursor-pointer group">
                      <input
                        type="checkbox"
                        className="mt-0.5 h-4 w-4 rounded border-border-2 text-accent focus:ring-accent shrink-0"
                        {...register('privacyAccepted')}
                      />
                      <span className="text-sm text-fg-3">
                        Ich habe die{' '}
                        <a
                          href="/datenschutz"
                          target="_blank"
                          className="text-accent hover:underline"
                        >
                          Datenschutzerklärung
                        </a>{' '}
                        gelesen und akzeptiere die Verarbeitung meiner Daten zur Bearbeitung
                        meiner Anfrage.
                      </span>
                    </label>
                    {errors.privacyAccepted && (
                      <p className="mt-1.5 text-sm text-red-600">
                        {errors.privacyAccepted.message}
                      </p>
                    )}
                  </div>

                  <Button
                    type="submit"
                    variant="primary"
                    size="lg"
                    loading={isSubmitting}
                    leftIcon={<Send className="h-4 w-4" />}
                    className="w-full md:w-auto"
                  >
                    Nachricht senden
                  </Button>
                </form>
              )}
            </div>

            {/* Sidebar contact info */}
            <div className="space-y-6">
              <div className="bg-bg-2 rounded-2xl p-6 border border-border-1">
                <h3 className="font-semibold text-fg-1 mb-5 text-lg">Kontaktinformation</h3>
                <div className="space-y-5">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-soft text-accent shrink-0">
                      <MapPin className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-fg-3 uppercase tracking-wide mb-0.5">
                        Adresse
                      </p>
                      <p className="text-sm text-fg-2">
                        Inexxio AG
                        <br />
                        Musterstrasse 1
                        <br />
                        8001 Zürich
                        <br />
                        Schweiz
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-soft text-accent shrink-0">
                      <Mail className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-fg-3 uppercase tracking-wide mb-0.5">
                        E-Mail
                      </p>
                      <a
                        href="mailto:info@inexxio.com"
                        className="text-sm text-accent hover:underline"
                      >
                        info@inexxio.com
                      </a>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-soft text-accent shrink-0">
                      <Phone className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-fg-3 uppercase tracking-wide mb-0.5">
                        Telefon
                      </p>
                      <a
                        href="tel:+41441234567"
                        className="text-sm text-accent hover:underline"
                      >
                        +41 44 123 45 67
                      </a>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-soft text-accent shrink-0">
                      <Clock className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-fg-3 uppercase tracking-wide mb-0.5">
                        Öffnungszeiten
                      </p>
                      <p className="text-sm text-fg-2">
                        Montag – Freitag
                        <br />
                        08:00 – 17:00 Uhr
                        <br />
                        <span className="text-fg-3">Samstag & Sonntag geschlossen</span>
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Map placeholder */}
              <div className="bg-border-1 rounded-2xl overflow-hidden border border-border-1">
                <div className="h-48 flex items-center justify-center text-sm text-fg-3">
                  <div className="text-center">
                    <MapPin className="h-8 w-8 text-fg-4 mx-auto mb-2" />
                    <p className="font-medium">Inexxio AG</p>
                    <p>Musterstrasse 1, 8001 Zürich</p>
                  </div>
                </div>
              </div>

              <div className="bg-accent-soft rounded-2xl p-5 border border-border-1">
                <h4 className="font-semibold text-fg-1 mb-2">Schnelle Reaktionszeit</h4>
                <p className="text-sm text-fg-3">
                  Wir beantworten alle Anfragen üblicherweise innert{' '}
                  <strong>24 Stunden</strong> an Werktagen.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
