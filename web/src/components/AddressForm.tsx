import { useState, type FormEvent } from "react";

import type { BillingAddress } from "../api/client";
import type { MessageKey } from "../i18n/en";
import { useI18n } from "../i18n/context";
import { Button, ProblemNotice } from "./ui";

type Field = {
  name: keyof BillingAddress;
  label: MessageKey;
  placeholder?: MessageKey;
  wide?: boolean;
  latin?: boolean;
};

const ADDRESS_FIELDS: Field[] = [
  { name: "name", label: "field.name", wide: true },
  { name: "phone", label: "field.phone", placeholder: "placeholder.phone", latin: true },
  { name: "email", label: "field.email", latin: true },
  { name: "street", label: "field.street", wide: true },
  { name: "building_number", label: "field.building_number", placeholder: "placeholder.digits4", latin: true },
  { name: "district", label: "field.district" },
  { name: "city", label: "field.city" },
  { name: "postal_code", label: "field.postal_code", placeholder: "placeholder.digits5", latin: true },
];

const BUSINESS_FIELDS: Field[] = [
  { name: "company_name", label: "field.company_name", wide: true },
  { name: "vat_number", label: "field.vat_number", placeholder: "placeholder.digits15", latin: true },
  { name: "cr_number", label: "field.cr_number", placeholder: "placeholder.digits10", latin: true },
];

type Props = {
  title: string;
  submitLabel: string;
  initial: Partial<BillingAddress>;
  business?: boolean;
  saved: boolean;
  busy: boolean;
  error: unknown;
  onSubmit: (address: BillingAddress) => void;
};

export function AddressForm({ title, submitLabel, initial, business = false, saved, busy, error, onSubmit }: Props) {
  const { t } = useI18n();
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
        {saved ? <span className="text-xs font-semibold text-ok">{t("checkout.saved")}</span> : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {fields.map((field) => (
          <label key={field.name} className={`text-sm ${field.wide ? "sm:col-span-2" : ""}`}>
            <span className="mb-1 block text-xs font-semibold text-muted">{t(field.label)}</span>
            <input
              value={(values[field.name] as string | undefined) ?? ""}
              dir={field.latin ? "ltr" : undefined}
              placeholder={field.placeholder ? t(field.placeholder) : undefined}
              onChange={(event) => setValues((current) => ({ ...current, [field.name]: event.target.value }))}
              className={`w-full rounded-lg border border-line bg-paper px-3 py-2 text-start outline-none focus:border-accent ${
                field.latin ? "rtl:text-right" : ""
              }`}
            />
          </label>
        ))}
      </div>
      <ProblemNotice error={error} />
      <Button type="submit" variant="quiet" busy={busy}>
        {submitLabel}
      </Button>
    </form>
  );
}
