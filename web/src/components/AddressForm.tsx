import { useState, type FormEvent } from "react";

import type { BillingAddress } from "../api/client";
import { Button, ProblemNotice } from "./ui";

type Field = { name: keyof BillingAddress; label: string; placeholder?: string; wide?: boolean };

const ADDRESS_FIELDS: Field[] = [
  { name: "name", label: "Full name", wide: true },
  { name: "phone", label: "Mobile", placeholder: "+9665XXXXXXXX" },
  { name: "email", label: "Email" },
  { name: "street", label: "Street", wide: true },
  { name: "building_number", label: "Building no.", placeholder: "4 digits" },
  { name: "district", label: "District" },
  { name: "city", label: "City" },
  { name: "postal_code", label: "Postal code", placeholder: "5 digits" },
];

const BUSINESS_FIELDS: Field[] = [
  { name: "company_name", label: "Company name", wide: true },
  { name: "vat_number", label: "VAT number", placeholder: "15 digits" },
  { name: "cr_number", label: "CR number", placeholder: "10 digits" },
];

type Props = {
  title: string;
  initial: Partial<BillingAddress>;
  business?: boolean;
  saved: boolean;
  busy: boolean;
  error: unknown;
  onSubmit: (address: BillingAddress) => void;
};

export function AddressForm({ title, initial, business = false, saved, busy, error, onSubmit }: Props) {
  const [values, setValues] = useState<Partial<BillingAddress>>(initial);
  const fields = business ? [...ADDRESS_FIELDS, ...BUSINESS_FIELDS] : ADDRESS_FIELDS;

  function submit(event: FormEvent) {
    event.preventDefault();
    const cleaned = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== "" && value != null));
    onSubmit({ country: "SA", ...cleaned } as BillingAddress);
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">{title}</h2>
        {saved ? <span className="text-xs font-semibold text-ok">Saved</span> : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {fields.map((field) => (
          <label key={field.name} className={`text-sm ${field.wide ? "sm:col-span-2" : ""}`}>
            <span className="mb-1 block text-xs font-semibold text-muted">{field.label}</span>
            <input
              value={(values[field.name] as string | undefined) ?? ""}
              placeholder={field.placeholder}
              onChange={(event) => setValues((current) => ({ ...current, [field.name]: event.target.value }))}
              className="w-full rounded-lg border border-line bg-paper px-3 py-2 outline-none focus:border-accent"
            />
          </label>
        ))}
      </div>
      <ProblemNotice error={error} />
      <Button type="submit" variant="quiet" busy={busy}>
        Save {title.toLowerCase()}
      </Button>
    </form>
  );
}
