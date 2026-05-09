import { create } from "zustand";

interface InventoryFiltersStore {
  category: string | null;
  isActive: boolean | null;
  search: string;
  locationId: string | null;
  setCategory: (value: string | null) => void;
  setIsActive: (value: boolean | null) => void;
  setSearch: (value: string) => void;
  setLocationId: (value: string | null) => void;
  resetFilters: () => void;
}

export const useInventoryFiltersStore = create<InventoryFiltersStore>((set) => ({
  category: null,
  isActive: null,
  search: "",
  locationId: null,
  setCategory: (category) => set({ category }),
  setIsActive: (isActive) => set({ isActive }),
  setSearch: (search) => set({ search }),
  setLocationId: (locationId) => set({ locationId }),
  resetFilters: () =>
    set({
      category: null,
      isActive: null,
      search: "",
      locationId: null,
    }),
}));

