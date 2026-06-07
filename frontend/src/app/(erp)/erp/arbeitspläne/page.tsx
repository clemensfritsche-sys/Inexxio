'use client';

import Link from 'next/link';
import { ArrowRight, Wrench } from 'lucide-react';

export default function ArbeitsplaenePage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 mb-4">
        <Wrench className="h-7 w-7 text-slate-400" />
      </div>
      <h1 className="text-xl font-bold text-slate-900 mb-2">Arbeitspläne sind umgezogen</h1>
      <p className="text-sm text-slate-500 max-w-sm mb-6">
        Prozessschritte werden jetzt direkt im Artikel unter dem Tab&nbsp;
        <span className="font-medium text-slate-700">„Prozess"</span> verwaltet.
      </p>
      <Link
        href="/erp"
        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors"
        style={{ background: '#E51A14' }}
      >
        Zum ERP Feed
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
