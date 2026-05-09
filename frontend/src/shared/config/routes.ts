export const routes = {
  home: "/",
  login: "/login",
  register: "/register",
  dashboard: "/dashboard",
  companies: "/dashboard/companies",
  partners: "/dashboard/partners",
  agents: "/dashboard/agents",
  agentDetail: (id: string) => `/dashboard/agents/${id}`,
  invoices: "/dashboard/invoices",
  expenses: "/dashboard/expenses",
  inventory: "/dashboard/inventory",
} as const;

