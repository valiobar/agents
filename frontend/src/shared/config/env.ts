export const env = {
  gatewayUrl:
    process.env.GATEWAY_URL ??
    process.env.NEXT_PUBLIC_GATEWAY_URL ??
    "http://localhost:8000",
  publicGatewayUrl: process.env.NEXT_PUBLIC_GATEWAY_URL ?? "/gateway-api",
} as const;

