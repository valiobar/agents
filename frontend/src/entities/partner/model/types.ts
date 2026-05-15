export type PartnerKind = "client" | "supplier" | "both" | "other";

export interface Partner {
  id: string;
  user_id: string;
  company_id: string;
  kind: PartnerKind;
  name: string;
  registration_number: string;
  vat_number: string | null;
  city: string;
  country: string;
  address: string;
  accountable_person: string;
  email: string | null;
  phone: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PartnerListResponse {
  total_count: number;
  returned_count: number;
  offset: number;
  limit: number;
  truncated: boolean;
  next_offset: number | null;
  items: Partner[];
}
