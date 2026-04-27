import { create } from "zustand";

export interface Notification {
  id: string;
  message: string;
  type: "success" | "error" | "info";
}

interface NotificationStore {
  notifications: Notification[];
  addNotification: (message: string, type?: Notification["type"]) => void;
  dismissNotification: (id: string) => void;
}

export const useNotificationStore = create<NotificationStore>((set) => ({
  notifications: [],
  addNotification: (message, type = "info") =>
    set((state) => ({
      notifications: [
        ...state.notifications,
        { id: crypto.randomUUID(), message, type },
      ],
    })),
  dismissNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((item) => item.id !== id),
    })),
}));

