export function calculateInvoicePreview(
  items: Array<{
    quantity: string;
    unit_price: string;
    vat_rate: string;
  }>,
) {
  return items.reduce(
    (acc, item) => {
      const qty = Number(item.quantity);
      const unit = Number(item.unit_price);
      const rate = Number(item.vat_rate);
      const subtotal = (Number.isFinite(qty) ? qty : 0) * (Number.isFinite(unit) ? unit : 0);
      const vat = subtotal * (Number.isFinite(rate) ? rate : 0);
      return {
        subtotal: acc.subtotal + subtotal,
        vatTotal: acc.vatTotal + vat,
        total: acc.total + subtotal + vat,
      };
    },
    { subtotal: 0, vatTotal: 0, total: 0 },
  );
}

