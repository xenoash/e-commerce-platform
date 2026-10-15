import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";

import { apiFor } from "../api/client";
import { SessionContext, readSession, writeSession, type Session } from "./session-context";

export function SessionProvider({ store, children }: { store: string; children: ReactNode }) {
  const [session, setSession] = useState<Session>(() => readSession(store));
  const latest = useRef(session);

  const update = useCallback(
    (patch: Partial<Session>) => {
      const base = latest.current.store === store ? latest.current : readSession(store);
      const next = { ...base, ...patch, store };
      latest.current = next;
      writeSession(next);
      setSession(next);
    },
    [store],
  );

  const signOut = useCallback(
    () =>
      update({
        token: undefined,
        customerName: undefined,
        customerKind: undefined,
        cartId: undefined,
        cartToken: undefined,
      }),
    [update],
  );
  const forgetCart = useCallback(() => update({ cartId: undefined, cartToken: undefined }), [update]);
  const rememberOrder = useCallback(
    (orderId: string) => {
      const cartToken = latest.current.cartToken;
      if (cartToken) update({ orderTokens: { ...latest.current.orderTokens, [orderId]: cartToken } });
    },
    [update],
  );

  const api = useMemo(
    () => apiFor({ store, token: session.token, cartToken: session.cartToken }),
    [store, session.token, session.cartToken],
  );

  const value = useMemo(
    () => ({ session, api, update, signOut, forgetCart, rememberOrder }),
    [session, api, update, signOut, forgetCart, rememberOrder],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
