import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { orderAccessToken, useSession } from "../lib/session-context";
import { ApiProblem, apiFor, unwrap, type Address, type BillingAddress, type Cart, type Order } from "./client";

export function useStoreSettings() {
  const { api, session } = useSession();
  return useQuery({
    queryKey: ["store", session.store],
    queryFn: () => unwrap(api.GET("/api/v1/store")),
    staleTime: 60_000,
  });
}

export function useProducts() {
  const { api, session } = useSession();
  return useQuery({
    queryKey: ["products", session.store],
    queryFn: () => unwrap(api.GET("/api/v1/products", { params: { query: { limit: 60 } } })),
  });
}

export function usePaymentMethods() {
  const { api, session } = useSession();
  return useQuery({
    queryKey: ["payment-methods", session.store],
    queryFn: () => unwrap(api.GET("/api/v1/payment-methods")),
    staleTime: 60_000,
  });
}

function cartKey(store: string, cartId?: string) {
  return ["cart", store, cartId];
}

export function useCart() {
  const { api, session, forgetCart } = useSession();
  return useQuery({
    queryKey: cartKey(session.store, session.cartId),
    enabled: Boolean(session.cartId),
    queryFn: async () => {
      try {
        const cart = await unwrap(api.GET("/api/v1/carts/{cart_id}", { params: { path: { cart_id: session.cartId! } } }));
        if (cart.status === "converted" || cart.status === "abandoned") {
          forgetCart();
          return null;
        }
        return cart;
      } catch (error) {
        if (error instanceof ApiProblem && error.status === 404) forgetCart();
        throw error;
      }
    },
  });
}

export function useSuggestions(cart: Cart | undefined) {
  const { api, session } = useSession();
  return useQuery({
    queryKey: ["suggestions", session.store, cart?.id, cart?.version],
    enabled: Boolean(cart && cart.items.length),
    queryFn: () =>
      unwrap(api.GET("/api/v1/carts/{cart_id}/suggestions", { params: { path: { cart_id: cart!.id } } })),
  });
}

export function useCartMutations() {
  const { api, session, update } = useSession();
  const queryClient = useQueryClient();
  const store = (cart: Cart) => queryClient.setQueryData(cartKey(session.store, cart.id), cart);

  async function ensureCart(): Promise<{ cartId: string; cartToken?: string }> {
    if (session.cartId) return { cartId: session.cartId, cartToken: session.cartToken };
    const created = await unwrap(api.POST("/api/v1/carts"));
    const cartToken = created.cart_token ?? undefined;
    update({ cartId: created.id, cartToken });
    return { cartId: created.id, cartToken };
  }

  const path = (cart_id: string) => ({ params: { path: { cart_id } } });

  const addItem = useMutation({
    mutationFn: async ({ productId, quantity = 1 }: { productId: string; quantity?: number }) => {
      const { cartId, cartToken } = await ensureCart();
      return unwrap(
        api.POST("/api/v1/carts/{cart_id}/items", {
          ...path(cartId),
          body: { product_id: productId, quantity },
          headers: cartToken ? { "X-Cart-Token": cartToken } : undefined,
        }),
      );
    },
    onSuccess: store,
  });

  const setQuantity = useMutation({
    mutationFn: ({ cartId, itemId, quantity }: { cartId: string; itemId: string; quantity: number }) =>
      unwrap(
        api.PATCH("/api/v1/carts/{cart_id}/items/{item_id}", {
          params: { path: { cart_id: cartId, item_id: itemId } },
          body: { quantity },
        }),
      ),
    onSuccess: store,
  });

  const removeItem = useMutation({
    mutationFn: ({ cartId, itemId }: { cartId: string; itemId: string }) =>
      unwrap(api.DELETE("/api/v1/carts/{cart_id}/items/{item_id}", { params: { path: { cart_id: cartId, item_id: itemId } } })),
    onSuccess: store,
  });

  const applyCoupon = useMutation({
    mutationFn: ({ cartId, code }: { cartId: string; code: string }) =>
      unwrap(api.PUT("/api/v1/carts/{cart_id}/coupon", { ...path(cartId), body: { code } })),
    onSuccess: store,
  });

  const removeCoupon = useMutation({
    mutationFn: ({ cartId }: { cartId: string }) => unwrap(api.DELETE("/api/v1/carts/{cart_id}/coupon", path(cartId))),
    onSuccess: store,
  });

  const setShipping = useMutation({
    mutationFn: ({ cartId, address }: { cartId: string; address: Address }) =>
      unwrap(api.PUT("/api/v1/carts/{cart_id}/shipping-address", { ...path(cartId), body: address })),
    onSuccess: store,
  });

  const setBilling = useMutation({
    mutationFn: ({ cartId, address }: { cartId: string; address: BillingAddress }) =>
      unwrap(api.PUT("/api/v1/carts/{cart_id}/billing-address", { ...path(cartId), body: address })),
    onSuccess: store,
  });

  const setPaymentMethod = useMutation({
    mutationFn: ({ cartId, method }: { cartId: string; method: string }) =>
      unwrap(
        api.PUT("/api/v1/carts/{cart_id}/payment-method", {
          ...path(cartId),
          body: { method: method as "card" | "apple_pay" | "cod" | "net_terms" },
        }),
      ),
    onSuccess: store,
  });

  return { addItem, setQuantity, removeItem, applyCoupon, removeCoupon, setShipping, setBilling, setPaymentMethod };
}

export function useOrderApi(orderId: string | undefined) {
  const { session } = useSession();
  const cartToken = orderAccessToken(session, orderId);
  return useMemo(
    () => apiFor({ store: session.store, token: session.token, cartToken }),
    [session.store, session.token, cartToken],
  );
}

export function useOrder(orderId: string | undefined) {
  const { session } = useSession();
  const api = useOrderApi(orderId);
  return useQuery({
    queryKey: ["order", session.store, orderId],
    enabled: Boolean(orderId),
    queryFn: () => unwrap(api.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: orderId! } } })),
    refetchInterval: (query) => {
      const order = query.state.data as Order | undefined;
      if (!order) return false;
      const waiting = order.status === "pending_payment" || !order.invoice || order.invoice.status === "issued";
      return waiting ? 2000 : false;
    },
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  });
}

export function useInvoice(order: Order | undefined) {
  const { session } = useSession();
  const api = useOrderApi(order?.id);
  const ready = Boolean(order?.invoice && (order.invoice.kind === "simplified" || order.invoice.status === "cleared"));
  return useQuery({
    queryKey: ["invoice", session.store, order?.id, order?.invoice?.status],
    enabled: ready,
    retry: false,
    queryFn: () => unwrap(api.GET("/api/v1/orders/{order_id}/invoice", { params: { path: { order_id: order!.id } } })),
  });
}

export function useInvoiceXmlDownload(orderId: string | undefined, fileName: string | undefined) {
  const api = useOrderApi(orderId);
  return async () => {
    if (!orderId) return;
    const { data, response } = await api.GET("/api/v1/orders/{order_id}/invoice", {
      params: { path: { order_id: orderId }, query: { format: "xml" } },
      parseAs: "text",
    });
    if (!response.ok || typeof data !== "string") return;
    const url = URL.createObjectURL(new Blob([data], { type: "application/xml" }));
    const link = Object.assign(document.createElement("a"), { href: url, download: `${fileName ?? "invoice"}.xml` });
    link.click();
    URL.revokeObjectURL(url);
  };
}
