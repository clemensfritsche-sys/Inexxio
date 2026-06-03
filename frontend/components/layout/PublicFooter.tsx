import Link from "next/link";

export default function PublicFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="bg-gray-900 text-gray-400 py-12 px-4">
      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-8">
          <div>
            <p className="text-white font-semibold mb-3">Inexxio</p>
            <p className="text-sm">
              Enterprise Central System für produzierendes KMU.
            </p>
          </div>
          <div>
            <p className="text-white font-semibold mb-3">Unternehmen</p>
            <ul className="space-y-2 text-sm">
              <li><Link href="/impressum" className="hover:text-white transition-colors">Impressum</Link></li>
              <li><Link href="/agb" className="hover:text-white transition-colors">AGB</Link></li>
              <li><Link href="/datenschutz" className="hover:text-white transition-colors">Datenschutz</Link></li>
            </ul>
          </div>
          <div>
            <p className="text-white font-semibold mb-3">Produkte</p>
            <ul className="space-y-2 text-sm">
              <li><Link href="/shop" className="hover:text-white transition-colors">Online Shop</Link></li>
            </ul>
          </div>
          <div>
            <p className="text-white font-semibold mb-3">Kontakt</p>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="mailto:info@inexxio.com" className="hover:text-white transition-colors">
                  info@inexxio.com
                </a>
              </li>
              <li><Link href="/kontakt" className="hover:text-white transition-colors">Kontaktformular</Link></li>
            </ul>
          </div>
        </div>
        <div className="border-t border-gray-800 pt-6 text-center text-xs text-gray-500">
          © {year} Inexxio AG, Schweiz. Alle Rechte vorbehalten.
        </div>
      </div>
    </footer>
  );
}
