export interface CompanyListParams {
  [key: string]: string | number | boolean | null | undefined;
  limit?: number;
  offset?: number;
}

export const companyKeys = {
  all: ["companies"] as const,
  list: (params: CompanyListParams = {}) => [...companyKeys.all, "list", params] as const,
  detail: (companyId: string) => [...companyKeys.all, "detail", companyId] as const,
};
