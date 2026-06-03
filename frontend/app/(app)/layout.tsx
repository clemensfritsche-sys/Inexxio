import ERPSidebar from "@/components/layout/ERPSidebar";
import ERPTopbar from "@/components/layout/ERPTopbar";

export default function ERPLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen flex overflow-hidden bg-gray-50">
      <ERPSidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <ERPTopbar />
        <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
