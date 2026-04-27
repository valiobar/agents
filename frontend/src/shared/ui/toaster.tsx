"use client";

import { useEffect, useRef } from "react";
import { useNotificationStore } from "@/shared/store/notification-store";

const TOAST_TTL_MS = 4_000;

function toastClasses(type: "success" | "error" | "info") {
  switch (type) {
    case "success":
      return "border-emerald-500/20 bg-emerald-500/10 text-emerald-950 dark:text-emerald-50";
    case "error":
      return "border-red-500/20 bg-red-500/10 text-red-950 dark:text-red-50";
    case "info":
    default:
      return "border-border bg-card text-foreground";
  }
}

export function Toaster() {
  const notifications = useNotificationStore((s) => s.notifications);
  const dismissNotification = useNotificationStore((s) => s.dismissNotification);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  useEffect(() => {
    for (const n of notifications) {
      if (timersRef.current.has(n.id)) continue;
      const timer = globalThis.setTimeout(() => {
        dismissNotification(n.id);
        timersRef.current.delete(n.id);
      }, TOAST_TTL_MS);
      timersRef.current.set(n.id, timer);
    }
  }, [notifications, dismissNotification]);

  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      for (const timer of timers.values()) globalThis.clearTimeout(timer);
      timers.clear();
    };
  }, []);

  if (notifications.length === 0) return null;

  return (
    <div className="fixed right-4 top-4 z-50 flex w-[min(420px,calc(100vw-2rem))] flex-col gap-2">
      {notifications.map((n) => (
        <button
          key={n.id}
          type="button"
          onClick={() => {
            const timer = timersRef.current.get(n.id);
            if (timer) globalThis.clearTimeout(timer);
            timersRef.current.delete(n.id);
            dismissNotification(n.id);
          }}
          className={[
            "rounded-lg border px-4 py-3 text-left shadow-sm transition hover:shadow-md",
            toastClasses(n.type),
          ].join(" ")}
          aria-label="Dismiss notification"
        >
          <div className="text-sm leading-relaxed">{n.message}</div>
        </button>
      ))}
    </div>
  );
}

