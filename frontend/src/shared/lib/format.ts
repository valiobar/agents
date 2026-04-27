export function formatCurrency(value: string | number, currency = "EUR") {
  return new Intl.NumberFormat("bg-BG", {
    style: "currency",
    currency,
  }).format(Number(value));
}

export function formatDate(value: string | number | Date) {
  return new Intl.DateTimeFormat("bg-BG", {
    dateStyle: "medium",
  }).format(new Date(value));
}

export function formatPercent(value: string | number) {
  return new Intl.NumberFormat("bg-BG", {
    style: "percent",
    maximumFractionDigits: 2,
  }).format(Number(value));
}

export function formatFileSize(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"] as const;
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const size = bytes / Math.pow(1024, i);
  return `${size.toFixed(size >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

