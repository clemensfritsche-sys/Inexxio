import type { Metadata } from "next";
import ItemsView from "@/components/erp/ItemsView";

export const metadata: Metadata = { title: "Artikel" };

export default function ItemsPage() {
  return <ItemsView />;
}
