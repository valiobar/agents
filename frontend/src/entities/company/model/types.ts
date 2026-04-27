export interface Company {
  id: string;
  user_id: string;
  name: string;
  registration_number: string;
  vat_number: string | null;
  city: string;
  country: string;
  address: string;
  accountable_person: string;
  email: string | null;
  phone: string | null;
  logo_data_url: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}
