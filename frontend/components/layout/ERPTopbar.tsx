"use client";

import { Bell, Search } from "lucide-react";

export default function ERPTopbar() {
  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center px-4 gap-4">
      {/* Global search */}
      <div className="flex-1 max-w-md">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="search"
            placeholder="Suchen... (⌘K)"
            className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white"
          />
        </div>
      </div>

      <div className="flex items-center gap-2 ml-auto">
        {/* Notifications */}
        <button className="relative p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors">
          <Bell size={18} />
          {/* Unread badge */}
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
        </button>

        {/* User avatar placeholder */}
        <button className="w-8 h-8 rounded-full bg-brand-600 text-white text-xs font-semibold flex items-center justify-center">
          IN
        </button>
      </div>
    </header>
  );
}
