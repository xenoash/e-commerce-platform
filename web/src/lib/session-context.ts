import { createContext, useContext } from "react";

import type { Api } from "../api/client";

export type Session = {
  store: string;
  token?: string;
  customerName?: string;
  customerKind?: string;
  cartId?: string;
  cartToken?: string;
};

export type SessionContextValue = {
  session: Session;
  api: Api;
  update: (patch: Partial<Session>) => void;
  signOut: () => void;
  forgetCart: () => void;
};

export const SessionContext = createContext<SessionContextValue | null>(null);

const storageKey = (store: string) => `ecommerce-demo:session:${store}`;

export function readSession(store: string): Session {
  try {
    const raw = localStorage.getItem(storageKey(store));
    return raw ? { ...JSON.parse(raw), store } : { store };
  } catch {
    return { store };
  }
}

export function writeSession(session: Session) {
  try {
    localStorage.setItem(storageKey(session.store), JSON.stringify(session));
  } catch {
    return;
  }
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
