import { QRCodeSVG } from "qrcode.react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router";

import type { Invoice } from "../api/client";
import { useInvoice, useInvoiceXmlDownload, useOrder } from "../api/hooks";
import { Button, Card, ProblemNotice, StatusBadge } from "../components/ui";
import { formatMoney } from "../lib/money";
import { useSession } from "../lib/session-context";

const TITLES = {
  simplified: { en: "Simplified Tax Invoice", ar: "فاتورة ضريبية مبسطة" },
  standard: { en: "Tax Invoice", ar: "فاتورة ضريبية" },
};

const issuedFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Riyadh",
  dateStyle: "medium",
  timeStyle: "short",
});

function Bilingual({ en, ar, className = "" }: { en: string; ar: string; className?: string }) {
  return (
    <span className={`flex items-baseline justify-between gap-3 ${className}`}>
      <span className="whitespace-nowrap">{en}</span>
      <span lang="ar" dir="rtl" className="whitespace-nowrap">
        {ar}
      </span>
    </span>
  );
}

function Field({ en, ar, children }: { en: string; ar: string; children: ReactNode }) {
  return (
    <div className="border-b border-line py-1.5 last:border-0">
      <Bilingual en={en} ar={ar} className="text-[11px] font-semibold uppercase tracking-wide text-muted" />
      <div className="mt-0.5 text-sm text-ink">{children}</div>
    </div>
  );
}

function TotalRow({ en, ar, amount, grand = false }: { en: string; ar: string; amount: string; grand?: boolean }) {
  return (
    <div className={`flex items-start justify-between gap-4 ${grand ? "border-t-2 border-ink pt-2 text-base font-bold" : ""}`}>
      <dt>
        <span className="block">{en}</span>
        <span lang="ar" dir="rtl" className="block text-left text-xs font-normal text-muted">
          {ar}
        </span>
      </dt>
      <dd>{money(amount)}</dd>
    </div>
  );
}

function addressLines(address: { street: string; building_number: string; district: string; city: string; postal_code: string } | null) {
  if (!address) return null;
  return (
    <>
      {address.building_number} {address.street}, {address.district}
      <br />
      {address.city} {address.postal_code}, Saudi Arabia
    </>
  );
}

function money(amount: string) {
  return <span className="tabular whitespace-nowrap">{formatMoney(amount)}</span>;
}

function InvoiceDocument({ invoice }: { invoice: Invoice }) {
  const title = TITLES[invoice.kind];
  const buyer = invoice.buyer;
  const columns: [string, string, string][] = [
    ["Description", "الوصف", "text-left"],
    ["Qty", "الكمية", "text-right"],
    ["Unit price", "سعر الوحدة", "text-right"],
    ["Taxable amount", "المبلغ الخاضع للضريبة", "text-right"],
    ["VAT", "الضريبة", "text-right"],
    ["Total incl. VAT", "الإجمالي شامل الضريبة", "text-right"],
  ];

  return (
    <article className="mx-auto max-w-[820px] rounded-2xl border border-line bg-surface p-8 text-ink shadow-sm print:max-w-none print:rounded-none print:border-0 print:p-0 print:shadow-none">
      <header className="flex flex-col gap-6 border-b-2 border-ink pb-6 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xl font-bold">{invoice.seller.legal_name}</p>
          <p className="mt-1 text-sm text-muted">{addressLines(invoice.seller)}</p>
          <p className="mt-2 text-sm">
            VAT <span className="font-mono">{invoice.seller.vat_number}</span> · CR{" "}
            <span className="font-mono">{invoice.seller.cr_number}</span>
          </p>
        </div>
        <div className="sm:text-right">
          <p className="text-2xl font-bold tracking-tight">{title.en}</p>
          <p lang="ar" dir="rtl" className="text-2xl font-bold">
            {title.ar}
          </p>
          <p className="mt-2 font-mono text-sm">{invoice.number}</p>
        </div>
      </header>

      <section className="grid gap-6 py-6 sm:grid-cols-2">
        <div>
          <Bilingual en="Invoice details" ar="بيانات الفاتورة" className="mb-1 text-sm font-bold" />
          <Field en="Issue date" ar="تاريخ الإصدار">
            {issuedFormat.format(new Date(invoice.issued_at))}
          </Field>
          <Field en="Order number" ar="رقم الطلب">
            <span className="font-mono">{invoice.order_number}</span>
          </Field>
          {invoice.po_number ? (
            <Field en="Purchase order" ar="أمر الشراء">
              <span className="font-mono">{invoice.po_number}</span>
            </Field>
          ) : null}
          <Field en="Invoice counter" ar="عداد الفاتورة">
            <span className="font-mono">{invoice.icv}</span>
          </Field>
        </div>
        <div>
          <Bilingual en="Buyer" ar="المشتري" className="mb-1 text-sm font-bold" />
          <Field en="Name" ar="الاسم">
            {buyer.name || "Cash customer"}
          </Field>
          {buyer.vat_number ? (
            <Field en="VAT number" ar="الرقم الضريبي">
              <span className="font-mono">{buyer.vat_number}</span>
            </Field>
          ) : null}
          {buyer.cr_number ? (
            <Field en="CR number" ar="السجل التجاري">
              <span className="font-mono">{buyer.cr_number}</span>
            </Field>
          ) : null}
          {buyer.address ? (
            <Field en="Address" ar="العنوان">
              {addressLines(buyer.address)}
            </Field>
          ) : null}
        </div>
      </section>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-y border-ink bg-paper">
              {columns.map(([en, ar, align]) => (
                <th key={en} className={`px-2 py-2 font-semibold ${align}`}>
                  <span className="block">{en}</span>
                  <span lang="ar" dir="rtl" className="block text-xs font-normal text-muted">
                    {ar}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {invoice.lines.map((line, index) => (
              <tr key={`${line.name}-${index}`} className="border-b border-line">
                <td className="px-2 py-2">{line.name}</td>
                <td className="px-2 py-2 text-right tabular">{line.quantity}</td>
                <td className="px-2 py-2 text-right">{money(line.unit_price)}</td>
                <td className="px-2 py-2 text-right">{money(line.net)}</td>
                <td className="px-2 py-2 text-right">
                  {money(line.vat)}
                  <span className="block text-xs text-muted">{Number(line.vat_rate)}%</span>
                </td>
                <td className="px-2 py-2 text-right font-semibold">{money(line.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="mt-6 flex flex-col-reverse gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-end gap-4">
          <div className="rounded-lg border border-line bg-white p-2">
            <QRCodeSVG value={invoice.qr_code} size={132} level="M" />
          </div>
          <div className="max-w-44 text-xs text-muted">
            <p>Scan with the ZATCA app to verify this invoice.</p>
            <p lang="ar" dir="rtl" className="mt-1">
              امسح الرمز للتحقق من الفاتورة عبر تطبيق هيئة الزكاة والضريبة والجمارك.
            </p>
          </div>
        </div>
        <dl className="w-full shrink-0 space-y-2 text-sm sm:w-72">
          <TotalRow en="Total excl. VAT" ar="الإجمالي غير شامل الضريبة" amount={invoice.taxable_amount} />
          <TotalRow en="Total VAT" ar="إجمالي الضريبة" amount={invoice.vat_total} />
          <TotalRow en="Total incl. VAT" ar="الإجمالي شامل الضريبة" amount={invoice.total} grand />
        </dl>
      </section>

      <footer className="mt-8 border-t border-line pt-4 text-[11px] text-muted">
        <p className="break-all font-mono">UUID {invoice.uuid}</p>
        <p className="break-all font-mono">Hash {invoice.invoice_hash}</p>
      </footer>
    </article>
  );
}

export function InvoicePage() {
  const { orderId } = useParams();
  const { session } = useSession();
  const orderQuery = useOrder(orderId);
  const order = orderQuery.data;
  const invoiceQuery = useInvoice(order);
  const invoice = invoiceQuery.data;
  const downloadXml = useInvoiceXmlDownload(order?.id, order?.invoice?.number);

  if (orderQuery.error) return <ProblemNotice error={orderQuery.error} />;

  return (
    <div className="space-y-4">
      <div className="mx-auto flex max-w-[820px] flex-wrap items-center gap-3 print:hidden">
        <Link to={`/${session.store}/orders/${orderId}`} className="text-sm text-muted hover:text-ink">
          Back to the order
        </Link>
        {order?.invoice ? <StatusBadge status={order.invoice.status} /> : null}
        <div className="ml-auto flex gap-2">
          <Button variant="quiet" onClick={downloadXml} disabled={!invoice}>
            Download signed XML
          </Button>
          <Button onClick={() => window.print()} disabled={!invoice}>
            Print or save as PDF
          </Button>
        </div>
      </div>
      {invoice ? (
        <InvoiceDocument invoice={invoice} />
      ) : (
        <Card className="mx-auto max-w-[820px]">
          <p className="text-sm text-muted">
            {order?.invoice?.kind === "standard"
              ? "This tax invoice is waiting for ZATCA clearance and will appear here once cleared."
              : "The invoice is being issued. This page updates on its own."}
          </p>
          <ProblemNotice error={invoiceQuery.error} />
        </Card>
      )}
    </div>
  );
}
