import { useMutation, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useRef } from "react";
import { Link, useParams } from "react-router";

import { unwrap, type Invoice, type Order } from "../api/client";
import { useInvoice, useOrder } from "../api/hooks";
import { Button, Card, Money, ProblemNotice, StatusBadge } from "../components/ui";
import { displayLineAmount, paymentLabel } from "../lib/labels";
import { useSession } from "../lib/session-context";

function useConfirmOnReturn(order: Order | undefined) {
  const { api, session } = useSession();
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
  const { api } = useSession();

  async function downloadXml() {
    const { data, response } = await api.GET("/api/v1/orders/{order_id}/invoice", {
      params: { path: { order_id: order.id }, query: { format: "xml" } },
      parseAs: "text",
    });
    if (!response.ok || typeof data !== "string") return;
    const url = URL.createObjectURL(new Blob([data], { type: "application/xml" }));
    const link = Object.assign(document.createElement("a"), { href: url, download: `${order.invoice?.number}.xml` });
    link.click();
    URL.revokeObjectURL(url);
  }

  if (!order.invoice) {
    const fulfilled = order.status === "paid" || order.status === "confirmed";
    return (
      <Card>
        <h2 className="text-lg font-bold">Tax invoice</h2>
        <p className="mt-2 text-sm text-muted">
          {fulfilled ? "Issuing your ZATCA invoice..." : "An invoice is issued once the order is paid or confirmed."}
        </p>
      </Card>
    );
  }
  const awaitingClearance = order.invoice.kind === "standard" && order.invoice.status !== "cleared";
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-bold">{order.invoice.kind === "standard" ? "Standard tax invoice" : "Simplified tax invoice"}</h2>
        <StatusBadge status={order.invoice.status} />
      </div>
      {awaitingClearance ? (
        <p className="text-sm text-muted">Waiting for ZATCA clearance. It will appear here once cleared.</p>
      ) : invoice ? (
        <div className="flex flex-col gap-4">
          <div className="self-center rounded-xl bg-white p-3">
            <QRCodeSVG value={invoice.qr_code} size={168} level="M" />
          </div>
          <dl className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted">Number</dt>
            <dd className="font-mono">{invoice.number}</dd>
            <dt className="text-muted">Seller VAT</dt>
            <dd className="font-mono">{String(invoice.seller.vat_number)}</dd>
            {invoice.buyer.vat_number ? (
              <>
                <dt className="text-muted">Buyer VAT</dt>
                <dd className="font-mono">{String(invoice.buyer.vat_number)}</dd>
              </>
            ) : null}
            <dt className="text-muted">Counter (ICV)</dt>
            <dd className="font-mono">{invoice.icv}</dd>
            <dt className="text-muted">Hash</dt>
            <dd className="truncate font-mono text-xs" title={invoice.invoice_hash}>
              {invoice.invoice_hash}
            </dd>
            <dt className="text-muted">Total</dt>
            <dd>
              <Money amount={invoice.total} />
            </dd>
          </dl>
        </div>
      ) : null}
      {!awaitingClearance ? (
        <Button variant="quiet" onClick={downloadXml}>
          Download signed XML
        </Button>
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

  if (orderQuery.error) return <ProblemNotice error={orderQuery.error} />;
  if (!order) return <p className="text-sm text-muted">Loading order...</p>;

  const payment = order.payment;
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
      <div className="space-y-6">
        <Card className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">{order.number}</h1>
            <StatusBadge status={order.status} />
          </div>
          {payment ? (
            <p className="text-sm text-muted">
              {paymentLabel(payment.method, payment.gateway)}: <StatusBadge status={payment.status} />
            </p>
          ) : null}
          {order.status === "payment_failed" ? (
            <div className="rounded-lg bg-bad/10 p-3 text-sm text-bad">
              <p className="font-semibold">{payment?.failure_message || "The payment did not go through."}</p>
              <p className="mt-1">Your items are back in the cart and the stock was released.</p>
              <Link to={`/${session.store}/checkout`} className="mt-2 inline-block font-semibold underline">
                Try another payment
              </Link>
            </div>
          ) : null}
          {order.status === "pending_payment" ? (
            <p className="text-sm text-warn">Waiting for the payment result. This page refreshes on its own.</p>
          ) : null}
          <ProblemNotice error={confirm.error} />
        </Card>
        <Card>
          <h2 className="mb-3 text-lg font-bold">Items</h2>
          <ul className="divide-y divide-line text-sm">
            {order.lines.map((line) => (
              <li key={line.id} className="flex justify-between gap-3 py-2">
                <span>
                  {line.quantity} × {line.name}
                  <span className="ml-2 font-mono text-xs text-muted">{line.sku}</span>
                </span>
                <Money amount={displayLineAmount(line, order.totals.prices_include_vat)} currency={order.currency} />
              </li>
            ))}
          </ul>
          <dl className="mt-3 space-y-1 border-t border-line pt-3 text-sm">
            {Number(order.totals.discount) > 0 ? (
              <div className="flex justify-between text-ok">
                <dt>Discount {order.coupon_code ? `(${order.coupon_code})` : ""}</dt>
                <dd>
                  -<Money amount={order.totals.discount} currency={order.currency} />
                </dd>
              </div>
            ) : null}
            <div className="flex justify-between">
              <dt className="text-muted">Shipping</dt>
              <dd>
                {Number(order.totals.shipping) === 0 ? "Free" : <Money amount={order.totals.shipping} currency={order.currency} />}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">VAT {Number(order.totals.vat_rate)}%</dt>
              <dd>
                <Money amount={order.totals.vat} currency={order.currency} />
              </dd>
            </div>
            <div className="flex justify-between text-base font-bold">
              <dt>Total</dt>
              <dd>
                <Money amount={order.totals.total} currency={order.currency} />
              </dd>
            </div>
          </dl>
          {order.po_number ? <p className="mt-3 text-xs text-muted">Purchase order {order.po_number}</p> : null}
        </Card>
      </div>
      <aside className="space-y-6">
        <InvoiceCard order={order} invoice={invoice} />
        <Link to={`/${session.store}`} className="block text-center text-sm font-semibold text-accent">
          Continue shopping
        </Link>
      </aside>
    </div>
  );
}
