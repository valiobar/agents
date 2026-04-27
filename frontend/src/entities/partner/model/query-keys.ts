import type { PartnerKind } from "./types";

export interface PartnerListParams {
  [key: string]: string | number | boolean | null | undefined;
  company_id?: string;
  kind?: PartnerKind;
  query?: string;
  limit?: number;
  offset?: number;
}

export const partnerKeys = {
  all: ["partners"] as const,
  list: (params: PartnerListParams = {}) => [...partnerKeys.all, "list", params] as const,
  detail: (partnerId: string, companyId?: string) =>
    [...partnerKeys.all, "detail", partnerId, companyId] as const,
};
