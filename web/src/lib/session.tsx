import { useCallback, useMemo, useState, type ReactNode } from "react";

import { apiFor } from "../api/client";
import { SessionContext, readSession, writeSession, type Session } from "./session-context";

export function SessionProvider({ store, children }: { store: string; children: ReactNode }) {
  const [session, setSession] = useState<Session>(() => readSession(store));
  const current = session.store === store ? session : readSession(store);

  const update = useCallback(
    (patch: Partial<Session>) => {
      setSession((previous) => {
        const base = previous.store === store ? previous : readSession(store);
        const next = { ...base, ...patch, store };
        writeSession(next);
        return next;
      });
    },
    [store],
  );

  const signOut = useCallback(() => update({ token: undefined, customerName: undefined, customerKind: undefined, cartId: undefined, cartToken: undefined }), [update]);
  const forgetCart = useCallback(() => update({ cartId: undefined, cartToken: undefined }), [update]);

  const api = useMemo(
    () => apiFor({ store, token: current.token, cartToken: current.cartToken }),
    [store, current.token, current.cartToken],
  );

  const value = useMemo(() => ({ session: current, api, update, signOut, forgetCart }), [current, api, update, signOut, forgetCart]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
