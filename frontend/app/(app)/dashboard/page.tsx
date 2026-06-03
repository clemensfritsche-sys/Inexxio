import type { Metadata } from "next";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {kpis.map((kpi) => (
          <div key={kpi.label} className="card p-4">
            <p className="text-sm text-gray-500">{kpi.label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{kpi.value}</p>
            {kpi.sub && <p className="text-xs text-gray-400 mt-0.5">{kpi.sub}</p>}
          </div>
        ))}
      </div>

      <div className="card p-6 text-center text-gray-400">
        <p className="text-sm">Phase 1 – Weitere Kennzahlen folgen</p>
      </div>
    </div>
  );
}

const kpis = [
  { label: "Artikel", value: "–", sub: "Noch keine Daten" },
  { label: "Offene Bestellungen", value: "–", sub: "Noch keine Daten" },
  { label: "Laufende Produktionen", value: "–", sub: "Noch keine Daten" },
  { label: "Offene Rechnungen", value: "–", sub: "Noch keine Daten" },
];
