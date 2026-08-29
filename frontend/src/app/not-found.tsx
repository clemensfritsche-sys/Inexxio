import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-white flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="text-8xl font-bold text-border-1 mb-4">404</div>
        <h1 className="text-2xl font-bold text-fg-1 mb-2">Seite nicht gefunden</h1>
        <p className="text-fg-3 mb-8">
          Die gesuchte Seite existiert nicht oder wurde verschoben.
        </p>
        <Link
          href="/"
          className="bg-inexxio hover:bg-inexxio-deep text-white px-6 py-3 rounded-lg font-medium transition-colors inline-block"
        >
          Zur Startseite
        </Link>
      </div>
    </div>
  );
}
