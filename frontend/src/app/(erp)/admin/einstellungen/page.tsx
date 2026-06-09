import { SystemConfigSection } from '@/components/account/sections/system-config-section';
import { ObjekttypenSection } from '@/components/account/sections/objekttypen-section';

export default function EinstellungenPage() {
  return (
    <div className="p-4 sm:p-6 max-w-3xl mx-auto space-y-6">
      <ObjekttypenSection />
      <SystemConfigSection />
    </div>
  );
}
