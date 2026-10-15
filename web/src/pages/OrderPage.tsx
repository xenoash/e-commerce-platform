import { useMutation, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useRef } from "react";
import { Link, useParams } from "react-router";

import { unwrap, type Invoice, type Order } from "../api/client";
import { useInvoice, useInvoiceXmlDownload, useOrder, useOrderApi } from "../api/hooks";
import { Button, Card, Money, ProblemNotice, StatusBadge } from "../components/ui";
import { useI18n } from "../i18n/context";
import { displayLineAmount, paymentLabel, productName } from "../lib/labels";
import { useSession } from "../lib/session-context";

function useConfirmOnReturn(order: Order | undefined) {
  const { session } = useSession();
  const api = useOrderApi(order?.id);
  const queryClient = useQueryClient();
  const attempted = useRef(false);
  const confirm = useMutation({
    mutationFn: (orderId: string) =>
      unwrap(api.POST("/api/v1/orders/{order_id}/payment/confirm", { params: { path: { order_id: orderId } } })),
    onSuccess: (updated) => queryClient.setQueryData(["order", session.store, updated.id], updated),
  });
  const waiting = order?.status === "pending_payment";
  useEffect(() => {
    if (order && waiting && !attempted.current) {
      attempted.current = true;
      confirm.mutate(order.id);
    }
  }, [order, waiting, confirm]);
  return confirm;
}

function InvoiceCard({ order, invoice }: { order: Order; invoice: Invoice | undefined }) {
  const { t } = useI18n();
  const downloadXml = useInvoiceXmlDownload(order.id, order.invoice?.number);
  const { session } = useSession();

  if (!order.invoice) {
    const fulfilled = order.status === "paid" || order.status === "confirmed";
    return (
      <Card>
        <h2 className="text-lg font-bold">{t("invoice.title")}</h2>
        <p className="mt-2 text-sm text-muted">{fulfilled ? t("invoice.issuing") : t("invoice.notYet")}</p>
      </Card>
    );
  }
  const awaitingClearance = order.invoice.kind === "standard" && order.invoice.status !== "cleared";
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-bold">{t(order.invoice.kind === "standard" ? "invoice.standard" : "invoice.simplified")}</h2>
        <StatusBadge status={order.invoice.status} kind="invoice" />
      </div>
      {awaitingClearance ? (
        <p className="text-sm text-muted">{t("invoice.awaitingClearance")}</p>
      ) : invoice ? (
        <div className="flex flex-col gap-4">
          <div className="self-center rounded-xl bg-white p-3">
            <QRCodeSVG value={invoice.qr_code} size={168} level="M" />
          </div>
          <dl className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted">{t("invoice.number")}</dt>
            <dd dir="ltr" className="font-mono rtl:text-right">
              {invoice.number}
            </dd>
            <dt className="text-muted">{t("invoice.sellerVat")}</dt>
            <dd dir="ltr" className="font-mono rtl:text-right">
              {invoice.seller.vat_number}
            </dd>
            {invoice.buyer.vat_number ? (
              <>
                <dt className="text-muted">{t("invoice.buyerVat")}</dt>
                <dd dir="ltr" className="font-mono rtl:text-right">
                  {invoice.buyer.vat_number}
                </dd>
              </>
            ) : null}
            <dt className="text-muted">{t("invoice.counter")}</dt>
            <dd className="font-mono">{invoice.icv}</dd>
            <dt className="text-muted">{t("invoice.hash")}</dt>
            <dd dir="ltr" className="truncate font-mono text-xs rtl:text-right" title={invoice.invoice_hash}>
              {invoice.invoice_hash}
            </dd>
            <dt className="text-muted">{t("invoice.total")}</dt>
            <dd>
              <Money amount={invoice.total} />
            </dd>
          </dl>
        </div>
      ) : null}
      {!awaitingClearance && invoice ? (
        <div className="flex flex-wrap gap-2">
          <Link
            to={`/${session.store}/orders/${order.id}/invoice`}
            className="inline-flex items-center rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink hover:opacity-90"
          >
            {t("invoice.view")}
          </Link>
          <Button variant="quiet" onClick={downloadXml}>
            {t("invoice.downloadXml")}
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

export function OrderPage() {
  const { orderId } = useParams();
  const { session } = useSession();
  const orderQuery = useOrder(orderId);
  const order = orderQuery.data;
  const confirm = useConfirmOnReturn(order);
  const invoice = useInvoice(order).data;
  const i18n = useI18n();
  const { t, has, lang } = i18n;

  if (orderQuery.error) return <ProblemNotice error={orderQuery.error} />;
  if (!order) return <p className="text-sm text-muted">{t("order.loading")}</p>;
  const failureKey = `paymentFailure.${order.payment?.failure_code ?? ""}`;

  const payment = order.payment;
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
      <div className="space-y-6">
        <Card className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <h1 dir="ltr" className="text-2xl font-bold tracking-tight">
              {order.number}
            </h1>
            <StatusBadge status={order.status} kind="order" />
          </div>
          {payment ? (
            <p className="text-sm text-muted">
              {paymentLabel(i18n, payment.method, payment.gateway)}: <StatusBadge status={payment.status} kind="payment" />
            </p>
          ) : null}
          {order.status === "payment_failed" ? (
            <div className="rounded-lg bg-bad/10 p-3 text-sm text-bad">
              <p className="font-semibold">{has(failureKey) ? t(failureKey) : t("order.failed")}</p>
              <p className="mt-1">{t("order.released")}</p>
              <Link to={`/${session.store}/checkout`} className="mt-2 inline-block font-semibold underline">
                {t("order.tryAgain")}
              </Link>
            </div>
          ) : null}
          {order.status === "pending_payment" ? (
            <p className="text-sm text-warn">{t("order.waiting")}</p>
          ) : null}
          <ProblemNotice error={confirm.error} />
        </Card>
        <Card>
          <h2 className="mb-3 text-lg font-bold">{t("order.items")}</h2>
          <ul className="divide-y divide-line text-sm">
            {order.lines.map((line) => (
              <li key={line.id} className="flex justify-between gap-3 py-2">
                <span>
                  {line.quantity} × {productName(lang, line)}
                  <span className="ms-2 font-mono text-xs text-muted">
                    <span dir="ltr">{line.sku}</span>
                  </span>
                </span>
                <Money amount={displayLineAmount(line, order.totals.prices_include_vat)} currency={order.currency} />
              </li>
            ))}
          </ul>
          <dl className="mt-3 space-y-1 border-t border-line pt-3 text-sm">
            {Number(order.totals.discount) > 0 ? (
              <div className="flex justify-between gap-3 text-ok">
                <dt>{order.coupon_code ? t("totals.discountWithCode", { code: order.coupon_code }) : t("totals.discount")}</dt>
                <dd>
                  <Money amount={order.totals.discount} currency={order.currency} negative />
                </dd>
              </div>
            ) : null}
            <div className="flex justify-between">
              <dt className="text-muted">{t("totals.shipping")}</dt>
              <dd>
                {Number(order.totals.shipping) === 0 ? t("totals.free") : <Money amount={order.totals.shipping} currency={order.currency} />}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">{t("totals.vat", { rate: Number(order.totals.vat_rate) })}</dt>
              <dd>
                <Money amount={order.totals.vat} currency={order.currency} />
              </dd>
            </div>
            <div className="flex justify-between text-base font-bold">
              <dt>{t("totals.total")}</dt>
              <dd>
                <Money amount={order.totals.total} currency={order.currency} />
              </dd>
            </div>
          </dl>
          {order.po_number ? <p className="mt-3 text-xs text-muted">{t("order.purchaseOrder", { po: order.po_number })}</p> : null}
        </Card>
      </div>
      <aside className="space-y-6">
        <InvoiceCard order={order} invoice={invoice} />
        <Link to={`/${session.store}`} className="block text-center text-sm font-semibold text-accent">
          {t("order.continue")}
        </Link>
      </aside>
    </div>
  );
}
