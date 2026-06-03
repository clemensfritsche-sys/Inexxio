"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Bell, Search, LogOut, Settings, User } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

export default function ERPTopbar() {
  const { userProfile, signOut } = useAuth();
  const router = useRouter();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleSignOut() {
    await signOut();
    router.push("/login");
  }

  const initials = userProfile
    ? `${userProfile.first_name?.[0] ?? ""}${userProfile.last_name?.[0] ?? ""}`.toUpperCase() || "?"
    : "?";

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
        </button>

        {/* User menu */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 hover:bg-gray-100 rounded-lg px-2 py-1 transition-colors"
          >
            {userProfile?.avatar_url ? (
              <img
                src={userProfile.avatar_url}
                alt="Avatar"
                className="w-8 h-8 rounded-full object-cover"
              />
            ) : (
              <div className="w-8 h-8 rounded-full bg-brand-600 text-white text-xs font-semibold flex items-center justify-center">
                {initials}
              </div>
            )}
            <span className="hidden md:block text-sm font-medium text-gray-700">
              {userProfile?.first_name ?? userProfile?.email ?? ""}
            </span>
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 top-full mt-1 w-52 bg-white rounded-xl shadow-lg border border-gray-200 py-1 z-50">
              <div className="px-3 py-2 border-b border-gray-100">
                <p className="text-sm font-medium text-gray-900">
                  {userProfile?.first_name} {userProfile?.last_name}
                </p>
                <p className="text-xs text-gray-400 truncate">{userProfile?.email}</p>
              </div>

              <button
                onClick={() => { setDropdownOpen(false); router.push("/app/profile"); }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                <User size={15} /> Profil
              </button>

              {userProfile?.role === "admin" && (
                <button
                  onClick={() => { setDropdownOpen(false); router.push("/app/admin"); }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  <Settings size={15} /> Admin
                </button>
              )}

              <div className="border-t border-gray-100 mt-1 pt-1">
                <button
                  onClick={handleSignOut}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                >
                  <LogOut size={15} /> Abmelden
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
