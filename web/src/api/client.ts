import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type Cart = Schemas["Cart"];
export type CartItem = Schemas["CartItemOut"];
export type Order = Schemas["Order"];
export type Product = Schemas["Product"];
export type Invoice = Schemas["Invoice"];
export type Suggestion = Schemas["Suggestion"];
export type Address = Schemas["AddressRequest"];
export type BillingAddress = Schemas["BillingAddressRequest"];
export type PaymentMethod = Schemas["PaymentMethod"];
export type StoreSettings = Schemas["Store"];

export type ProblemBody = {
  type: string;
  title: string;
  status: number;
  code: string;
  detail?: string;
  errors?: { field: string | null; code: string; message: string }[];
  [extra: string]: unknown;
};

export class ApiProblem extends Error {
  readonly status: number;
  readonly body: ProblemBody;

  constructor(status: number, body: ProblemBody) {
    super(body.detail ?? body.code);
    this.status = status;
    this.body = body;
  }

  get code() {
    return this.body.code;
  }
}

export type Credentials = {
  store: string;
  token?: string;
  cartToken?: string;
};

export function apiFor(credentials: Credentials) {
  const client = createClient<paths>({ baseUrl: "" });
  const scope: Middleware = {
    onRequest({ request }) {
      request.headers.set("X-Store", credentials.store);
      if (credentials.token) request.headers.set("Authorization", `Bearer ${credentials.token}`);
      if (credentials.cartToken) request.headers.set("X-Cart-Token", credentials.cartToken);
      return request;
    },
  };
  client.use(scope);
  return client;
}

export type Api = ReturnType<typeof apiFor>;

export async function unwrap<T>(call: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await call;
  if (!response.ok) {
    const body = (error ?? { code: "HTTP_ERROR", status: response.status, title: response.statusText, type: "about:blank" }) as ProblemBody;
    throw new ApiProblem(response.status, body);
  }
  return data as T;
}
