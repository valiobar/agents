import { Document, Font, Image, Page, StyleSheet, Text, View } from "@react-pdf/renderer";

import type { Invoice } from "@/entities/invoice/model/types";

const PDF_FONT_FAMILY = "Noto Sans";

Font.register({
  family: PDF_FONT_FAMILY,
  fonts: [
    { src: "/fonts/NotoSans-Regular.ttf", fontWeight: 400 },
    { src: "/fonts/NotoSans-Bold.ttf", fontWeight: 700 },
  ],
});

const styles = StyleSheet.create({
  page: {
    padding: 32,
    fontSize: 9,
    color: "#111827",
    fontFamily: PDF_FONT_FAMILY,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 18,
  },
  logo: {
    width: 90,
    height: 45,
    objectFit: "contain",
    marginRight: 12,
  },
  titleBlock: {
    flexGrow: 1,
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
  },
  muted: {
    color: "#6b7280",
  },
  section: {
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: 700,
    marginBottom: 6,
    textTransform: "uppercase",
  },
  grid: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  gridColumn: {
    width: "48%",
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 3,
  },
  partyBox: {
    padding: 8,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 3,
  },
  partyTitle: {
    fontSize: 11,
    fontWeight: 700,
    marginBottom: 6,
  },
  label: {
    color: "#6b7280",
    width: "42%",
  },
  value: {
    width: "58%",
    textAlign: "right",
  },
  metaGrid: {
    padding: 8,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 3,
  },
  table: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },
  tableRow: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: "#e5e7eb",
  },
  tableHeader: {
    backgroundColor: "#f3f4f6",
    fontWeight: 700,
  },
  descriptionCell: {
    width: "32%",
    padding: 4,
  },
  cell: {
    width: "11.33%",
    padding: 4,
    textAlign: "right",
  },
  notes: {
    padding: 8,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    minHeight: 32,
  },
  totals: {
    marginLeft: "55%",
  },
  totalRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  grandTotal: {
    fontSize: 14,
    fontWeight: 700,
    borderTopWidth: 1,
    borderTopColor: "#d1d5db",
    paddingTop: 8,
  },
});

function formatMoney(value: string | number, currency: Invoice["currency"]) {
  const amount = new Intl.NumberFormat("bg-BG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value));

  return `${amount} ${currency}`;
}

function formatDate(value: string | null) {
  if (!value) return "";

  return new Intl.DateTimeFormat("bg-BG", {
    dateStyle: "medium",
  }).format(new Date(value));
}

function formatPercent(value: string | number) {
  return new Intl.NumberFormat("bg-BG", {
    style: "percent",
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function paymentMethodLabel(method: Invoice["payment_method"]) {
  switch (method) {
    case "bank_transfer":
      return "Банков превод";
    case "cash":
      return "В брой";
    case "card":
      return "Карта";
    case "other":
      return "Друго";
    default:
      return "";
  }
}

function PartyBlock({
  title,
  party,
}: Readonly<{
  title: string;
  party: NonNullable<Invoice["supplier_snapshot"]>;
}>) {
  return (
    <View style={styles.partyBox}>
      <Text style={styles.partyTitle}>{title}</Text>
      <View style={styles.row}>
        <Text style={styles.label}>Име</Text>
        <Text style={styles.value}>{party.name ?? ""}</Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.label}>ЕИК</Text>
        <Text style={styles.value}>{party.registration_number ?? ""}</Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.label}>ДДС №</Text>
        <Text style={styles.value}>{party.vat_number ?? ""}</Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.label}>Адрес</Text>
        <Text style={styles.value}>{party.address ?? ""}</Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.label}>Град</Text>
        <Text style={styles.value}>{party.city ?? ""}</Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.label}>Държава</Text>
        <Text style={styles.value}>{party.country ?? ""}</Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.label}>МОЛ</Text>
        <Text style={styles.value}>{party.accountable_person ?? ""}</Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.label}>Имейл</Text>
        <Text style={styles.value}>{party.email ?? ""}</Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.label}>Телефон</Text>
        <Text style={styles.value}>{party.phone ?? ""}</Text>
      </View>
    </View>
  );
}

export function InvoicePdfDocument({ invoice }: Readonly<{ invoice: Invoice }>) {
  const supplier = invoice.supplier_snapshot;
  const recipient = invoice.recipient_snapshot;
  const canRenderFromSnapshots = Boolean(supplier && recipient);

  if (!supplier || !recipient) {
    return (
      <Document title={`Фактура ${invoice.invoice_number}`}>
        <Page size="A4" style={styles.page}>
          <View style={styles.header}>
            <View style={styles.titleBlock}>
              <Text style={styles.title}>Фактура</Text>
              <Text style={styles.muted}>№ {invoice.invoice_number}</Text>
              {invoice.original_label ? <Text style={styles.muted}>{invoice.original_label}</Text> : null}
            </View>
            <View>
              <Text style={styles.muted}>{invoice.currency}</Text>
            </View>
          </View>

          <View style={[styles.section, styles.partyBox]}>
            <Text style={styles.partyTitle}>Липсват snapshot данни</Text>
            <Text style={styles.muted}>
              Тази фактура е създадена преди добавянето на snapshot полетата. Генерирането на пълен PDF изисква
              backfill на доставчик/получател.
            </Text>
            <View style={{ height: 10 }} />
            <View style={styles.row}>
              <Text style={styles.label}>Контрагент</Text>
              <Text style={styles.value}>{invoice.counterparty ?? invoice.recipient_name ?? "-"}</Text>
            </View>
          </View>

          <View style={[styles.section, styles.metaGrid]}>
            <View style={styles.row}>
              <Text style={styles.label}>Дата на издаване</Text>
              <Text style={styles.value}>{formatDate(invoice.issue_date)}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.label}>Дата на данъчно събитие</Text>
              <Text style={styles.value}>{formatDate(invoice.tax_event_date)}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.label}>Място на сделката</Text>
              <Text style={styles.value}>{invoice.place_of_supply ?? ""}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.label}>Падеж</Text>
              <Text style={styles.value}>{formatDate(invoice.due_date)}</Text>
            </View>
          </View>
        </Page>
      </Document>
    );
  }

  return (
    <Document title={`Фактура ${invoice.invoice_number}`}>
      <Page size="A4" style={styles.page}>
        <View style={styles.header}>
          {supplier?.logo_data_url ? (
            // eslint-disable-next-line jsx-a11y/alt-text
            <Image src={supplier.logo_data_url} style={styles.logo} />
          ) : null}
          <View style={styles.titleBlock}>
            <Text style={styles.title}>Фактура</Text>
            <Text style={styles.muted}>№ {invoice.invoice_number}</Text>
            {invoice.original_label ? <Text style={styles.muted}>{invoice.original_label}</Text> : null}
          </View>
          <View>
            <Text style={styles.muted}>{invoice.currency}</Text>
          </View>
        </View>

        {canRenderFromSnapshots ? (
          <View style={[styles.section, styles.grid]}>
            <View style={styles.gridColumn}>
              <PartyBlock title="Доставчик" party={supplier} />
            </View>
            <View style={styles.gridColumn}>
              <PartyBlock title="Получател" party={recipient} />
            </View>
          </View>
        ) : null}

        <View style={[styles.section, styles.metaGrid]}>
          <View style={styles.row}>
            <Text style={styles.label}>Дата на издаване</Text>
            <Text style={styles.value}>{formatDate(invoice.issue_date)}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Дата на данъчно събитие</Text>
            <Text style={styles.value}>{formatDate(invoice.tax_event_date)}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Място на сделката</Text>
            <Text style={styles.value}>{invoice.place_of_supply ?? ""}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Падеж</Text>
            <Text style={styles.value}>{formatDate(invoice.due_date)}</Text>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Редове</Text>
          <View style={styles.table}>
            <View style={[styles.tableRow, styles.tableHeader]}>
              <Text style={styles.descriptionCell}>Описание</Text>
              <Text style={styles.cell}>Кол.</Text>
              <Text style={styles.cell}>Мярка</Text>
              <Text style={styles.cell}>Ед. цена</Text>
              <Text style={styles.cell}>ДДС</Text>
              <Text style={styles.cell}>Основа</Text>
              <Text style={styles.cell}>ДДС</Text>
              <Text style={styles.cell}>Сума</Text>
            </View>
            {invoice.items.map((item, index) => (
              <View key={`${item.description}-${index}`} style={styles.tableRow}>
                <Text style={styles.descriptionCell}>{item.description}</Text>
                <Text style={styles.cell}>{item.quantity}</Text>
                <Text style={styles.cell}>{item.unit_label}</Text>
                <Text style={styles.cell}>{formatMoney(item.unit_price, invoice.currency)}</Text>
                <Text style={styles.cell}>{formatPercent(item.vat_rate)}</Text>
                <Text style={styles.cell}>{formatMoney(item.subtotal, invoice.currency)}</Text>
                <Text style={styles.cell}>{formatMoney(item.vat_amount, invoice.currency)}</Text>
                <Text style={styles.cell}>{formatMoney(item.total, invoice.currency)}</Text>
              </View>
            ))}
          </View>
        </View>

        {invoice.notes ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Бележки</Text>
            <Text style={styles.notes}>{invoice.notes}</Text>
          </View>
        ) : null}

        <View style={[styles.section, styles.totals]}>
          <View style={styles.totalRow}>
            <Text>Данъчна основа</Text>
            <Text>{formatMoney(invoice.subtotal, invoice.currency)}</Text>
          </View>
          <View style={styles.totalRow}>
            <Text>ДДС</Text>
            <Text>{formatMoney(invoice.vat_total, invoice.currency)}</Text>
          </View>
          <View style={[styles.totalRow, styles.grandTotal]}>
            <Text>Сума за плащане</Text>
            <Text>{formatMoney(invoice.total, invoice.currency)}</Text>
          </View>
        </View>

        <View style={styles.section} wrap={false}>
          <View style={styles.row}>
            <Text style={styles.label}>Словом</Text>
            <Text style={styles.value}>{invoice.amount_in_words ?? ""}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Плащане</Text>
            <Text style={styles.value}>{paymentMethodLabel(invoice.payment_method)}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>IBAN</Text>
            <Text style={styles.value}>{invoice.bank_iban ?? ""}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>BIC</Text>
            <Text style={styles.value}>{invoice.bank_bic ?? ""}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Основание за неначисляване на ДДС</Text>
            <Text style={styles.value}>{invoice.vat_reason ?? ""}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Съставил</Text>
            <Text style={styles.value}>{invoice.compiler_name ?? ""}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Получил</Text>
            <Text style={styles.value}></Text>
          </View>
        </View>
      </Page>
    </Document>
  );
}
