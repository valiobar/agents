"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Building2, Handshake, LayoutDashboard, Receipt, Wallet, X } from "lucide-react";

import { routes } from "@/shared/config/routes";
import { cn } from "@/shared/lib/cn";
import { useUIStore } from "@/shared/store/ui-store";
import { Button } from "@/shared/ui/button";
import { ThemeToggle } from "@/shared/ui/theme-toggle";

const navItems = [
  { href: routes.dashboard, label: "Dashboard", icon: LayoutDashboard },
  { href: routes.companies, label: "Companies", icon: Building2 },
  { href: routes.partners, label: "Partners", icon: Handshake },
  { href: routes.agents, label: "Agents", icon: Bot },
  { href: routes.invoices, label: "Invoices", icon: Receipt },
  { href: routes.expenses, label: "Expenses", icon: Wallet },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const setSidebarOpen = useUIStore((s) => s.setSidebarOpen);

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/40 md:hidden",
          sidebarOpen ? "block" : "hidden",
        )}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      <aside
        className={cn(
          "fixed left-0 top-0 z-50 h-screen w-64 border-r bg-background",
          "transition-transform duration-200 md:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
        aria-label="Sidebar navigation"
      >
        <div className="flex h-full flex-col">
        <div className="flex h-16 items-center justify-between border-b px-4">
          <Link href={routes.dashboard} className="font-semibold tracking-tight">
            Agents
          </Link>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <nav className="flex-1 p-3">
          <ul className="space-y-1">
            {navItems.map((item) => {
              const active =
                pathname === item.href ||
                (item.href !== routes.dashboard && pathname.startsWith(item.href));
              const Icon = item.icon;

              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                      active
                        ? "bg-accent text-accent-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                    )}
                    onClick={() => setSidebarOpen(false)}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="border-t p-3">
          <div className="flex items-center justify-between rounded-md px-3 py-2 text-sm text-muted-foreground">
            <span>Theme</span>
            <ThemeToggle />
          </div>
        </div>
        </div>
      </aside>
    </>
  );
}

