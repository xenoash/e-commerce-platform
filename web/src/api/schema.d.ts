export interface paths {
    "/api/v1/auth/token": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sign in and get a store-scoped bearer token */
        post: operations["createToken"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/carts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Open a cart
         * @description Signed-in customers get their active cart back (200) or a new one (201). Guests always get a new cart and a one-time `cart_token`.
         */
        post: operations["createCart"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/carts/{cart_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get a cart with live prices, warnings and checkout readiness */
        get: operations["getCart"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/carts/{cart_id}/billing-address": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set the billing address; a VAT number makes the invoice a standard (B2B) tax invoice */
        put: operations["setBillingAddress"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/carts/{cart_id}/checkout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Place the order and start payment
         * @description Creates an order and charges the chosen payment method. Returns 201 with the order. When `payment.next_action` is present, send the shopper there (3-D Secure), then call `POST /orders/{id}/payment/confirm`. Retrying with the same Idempotency-Key replays the result.
         */
        post: operations["checkoutCart"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/carts/{cart_id}/coupon": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Apply a coupon (replaces any applied coupon) */
        put: operations["applyCoupon"];
        post?: never;
        /** Remove the coupon (no-op when none is applied) */
        delete: operations["removeCoupon"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/carts/{cart_id}/items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Add a product (merges into the existing line) */
        post: operations["addCartItem"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/carts/{cart_id}/items/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Remove a product */
        delete: operations["removeCartItem"];
        options?: never;
        head?: never;
        /** Change a line's quantity */
        patch: operations["updateCartItem"];
        trace?: never;
    };
    "/api/v1/carts/{cart_id}/payment-method": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Choose how to pay (the card token is sent at checkout, never stored on the cart) */
        put: operations["setPaymentMethod"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/carts/{cart_id}/shipping-address": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set the delivery address (Saudi national address) */
        put: operations["setShippingAddress"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/carts/{cart_id}/suggestions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Upsell and cross-sell suggestions for this cart */
        get: operations["listCartSuggestions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The signed-in customer */
        get: operations["getMe"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The signed-in customer's orders */
        get: operations["listOrders"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders/{order_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get an order with its payment and invoice status */
        get: operations["getOrder"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders/{order_id}/invoice": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The order's ZATCA tax invoice (JSON with QR payload, or ?format=xml for the signed UBL) */
        get: operations["getOrderInvoice"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders/{order_id}/payment/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Re-check payment with the gateway after a redirect (safe to call repeatedly) */
        post: operations["confirmOrderPayment"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/payment-methods": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Payment methods this store accepts */
        get: operations["listPaymentMethods"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/products": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Browse the store's catalogue */
        get: operations["listProducts"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/products/{product_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get one product */
        get: operations["getProduct"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/store": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Public settings of the current store */
        get: operations["getStore"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/webhooks/payments/{gateway}/{store}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Gateway callback. Signature-verified with the store's secret; duplicates are no-ops. */
        post: operations["receivePaymentWebhook"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        AddItemRequest: {
            /** Format: uuid */
            product_id: string;
            /** @default 1 */
            quantity: number;
        };
        Address: {
            name: string;
            phone: string;
            email?: string;
            street: string;
            building_number: string;
            additional_number?: string;
            district: string;
            city: string;
            postal_code: string;
            /**
             * @description Delivery is limited to Saudi Arabia.
             *
             *     * `SA` - SA
             * @default SA
             */
            country: components["schemas"]["CountryEnum"];
        };
        AddressRequest: {
            name: string;
            phone: string;
            email?: string;
            street: string;
            building_number: string;
            additional_number?: string;
            district: string;
            city: string;
            postal_code: string;
            /**
             * @description Delivery is limited to Saudi Arabia.
             *
             *     * `SA` - SA
             * @default SA
             */
            country: components["schemas"]["CountryEnum"];
        };
        ApplyCouponRequest: {
            code: string;
        };
        BillingAddress: {
            name: string;
            phone: string;
            email?: string;
            street: string;
            building_number: string;
            additional_number?: string;
            district: string;
            city: string;
            postal_code: string;
            /**
             * @description Delivery is limited to Saudi Arabia.
             *
             *     * `SA` - SA
             * @default SA
             */
            country: components["schemas"]["CountryEnum"];
            company_name?: string;
            vat_number?: string;
            cr_number?: string;
        };
        BillingAddressRequest: {
            name: string;
            phone: string;
            email?: string;
            street: string;
            building_number: string;
            additional_number?: string;
            district: string;
            city: string;
            postal_code: string;
            /**
             * @description Delivery is limited to Saudi Arabia.
             *
             *     * `SA` - SA
             * @default SA
             */
            country: components["schemas"]["CountryEnum"];
            company_name?: string;
            vat_number?: string;
            cr_number?: string;
        };
        Buyer: {
            kind: string;
            name: string;
            email: string;
            company_name: string;
            vat_number: string;
        };
        Cart: {
            /** Format: uuid */
            id: string;
            status: string;
            /** @description Send as If-Match to make a write conditional. */
            version: number;
            currency: string;
            customer: components["schemas"]["CustomerRef"] | null;
            items: components["schemas"]["CartItemOut"][];
            coupon: components["schemas"]["CartCoupon"] | null;
            shipping_address: components["schemas"]["Address"] | null;
            billing_address: components["schemas"]["BillingAddress"] | null;
            payment_method: components["schemas"]["PaymentMethodOut"] | null;
            invoice_kind: components["schemas"]["InvoiceKindEnum"];
            totals: components["schemas"]["Totals"];
            checkout_readiness: components["schemas"]["Readiness"];
            warnings: components["schemas"]["Warning"][];
            /** Format: date-time */
            created_at: string;
            /** Format: date-time */
            updated_at: string;
        };
        CartCoupon: {
            code: string;
            description: string;
            applicable: boolean;
            reason: components["schemas"]["CouponReason"] | null;
            /** Format: decimal */
            discount: string;
        };
        CartItemOut: {
            /** Format: uuid */
            id: string;
            product: components["schemas"]["ProductRef"];
            quantity: number;
            /** Format: decimal */
            unit_price: string;
            /** Format: decimal */
            subtotal: string;
            /** Format: decimal */
            discount: string;
            /**
             * Format: decimal
             * @description Taxable amount after discount.
             */
            net: string;
            /** Format: decimal */
            vat: string;
            /**
             * Format: decimal
             * @description Amount including VAT.
             */
            total: string;
            available: boolean;
        };
        CheckoutRequest: {
            /** @description Single-use token from the gateway's client SDK. */
            payment_token?: string | null;
            /**
             * Format: decimal
             * @description The total the shopper saw. Checkout fails with CART_TOTAL_CHANGED if it moved.
             */
            expected_total?: string | null;
            /** @default  */
            po_number: string;
        };
        /**
         * @description * `SA` - SA
         * @enum {string}
         */
        CountryEnum: "SA";
        CouponReason: {
            code: string;
            detail: string;
        };
        CreatedCart: {
            /** Format: uuid */
            id: string;
            status: string;
            /** @description Send as If-Match to make a write conditional. */
            version: number;
            currency: string;
            customer: components["schemas"]["CustomerRef"] | null;
            items: components["schemas"]["CartItemOut"][];
            coupon: components["schemas"]["CartCoupon"] | null;
            shipping_address: components["schemas"]["Address"] | null;
            billing_address: components["schemas"]["BillingAddress"] | null;
            payment_method: components["schemas"]["PaymentMethodOut"] | null;
            invoice_kind: components["schemas"]["InvoiceKindEnum"];
            totals: components["schemas"]["Totals"];
            checkout_readiness: components["schemas"]["Readiness"];
            warnings: components["schemas"]["Warning"][];
            /** Format: date-time */
            created_at: string;
            /** Format: date-time */
            updated_at: string;
            /** @description Guest carts only. Send it back as X-Cart-Token. Shown once. */
            cart_token: string | null;
        };
        Customer: {
            /** Format: uuid */
            id: string;
            /** Format: email */
            email: string;
            name: string;
            kind: string;
            company_name: string;
            vat_number: string;
            credit_approved: boolean;
            /** Format: decimal */
            credit_limit: string;
        };
        CustomerRef: {
            /** Format: uuid */
            id: string;
            name: string;
            kind: string;
        };
        FieldError: {
            field: string | null;
            code: string;
            message: string;
        };
        Invoice: {
            /** Format: uuid */
            id: string;
            number: string;
            doc_type: string;
            kind: components["schemas"]["InvoiceKindEnum"];
            /** @description issued, pending_retry, reported, cleared or rejected. */
            status: string;
            /** Format: uuid */
            uuid: string;
            /** @description Invoice counter value in the device's hash chain. */
            icv: number;
            invoice_hash: string;
            previous_invoice_hash: string;
            /** Format: date-time */
            issued_at: string;
            order_number: string;
            po_number: string;
            /** @description Original invoice, for credit notes. */
            billing_reference: string;
            /** @description Base64 TLV payload to render as a QR code. */
            qr_code: string;
            seller: components["schemas"]["InvoiceSeller"];
            buyer: components["schemas"]["InvoiceBuyer"];
            /** @description Read back from the signed XML, exactly as submitted. */
            lines: components["schemas"]["InvoiceLine"][];
            /** Format: decimal */
            taxable_amount: string;
            /** Format: decimal */
            vat_total: string;
            /** Format: decimal */
            total: string;
            zatca_warnings: {
                [key: string]: unknown;
            }[];
            xml_url: string;
        };
        InvoiceAddress: {
            street: string;
            building_number: string;
            district: string;
            city: string;
            postal_code: string;
            country: string;
        };
        InvoiceBuyer: {
            name: string;
            vat_number: string;
            cr_number: string;
            address: components["schemas"]["InvoiceAddress"] | null;
        };
        /**
         * @description * `simplified` - simplified
         *     * `standard` - standard
         * @enum {string}
         */
        InvoiceKindEnum: "simplified" | "standard";
        InvoiceLine: {
            name: string;
            quantity: number;
            /**
             * Format: decimal
             * @description Net unit price, excluding VAT.
             */
            unit_price: string;
            /** Format: decimal */
            net: string;
            /** Format: decimal */
            vat_rate: string;
            /** Format: decimal */
            vat: string;
            /** Format: decimal */
            total: string;
        };
        InvoiceSeller: {
            legal_name: string;
            vat_number: string;
            cr_number: string;
            street: string;
            building_number: string;
            district: string;
            city: string;
            postal_code: string;
            country: string;
        };
        InvoiceSummary: {
            /** Format: uuid */
            id: string;
            number: string;
            kind: string;
            status: string;
            /** Format: date-time */
            issued_at: string;
        };
        /**
         * @description * `card` - Card
         *     * `apple_pay` - Apple Pay
         *     * `cod` - Cod
         *     * `net_terms` - Net Terms
         * @enum {string}
         */
        MethodEnum: "card" | "apple_pay" | "cod" | "net_terms";
        /**
         * @description * `items` - items
         *     * `shipping_address` - shipping_address
         *     * `payment_method` - payment_method
         *     * `billing_address` - billing_address
         *     * `available_items` - available_items
         *     * `applicable_coupon` - applicable_coupon
         * @enum {string}
         */
        MissingEnum: "items" | "shipping_address" | "payment_method" | "billing_address" | "available_items" | "applicable_coupon";
        NextAction: {
            type: components["schemas"]["NextActionTypeEnum"];
            /** Format: uri */
            url: string;
        };
        /**
         * @description * `redirect` - redirect
         * @enum {string}
         */
        NextActionTypeEnum: "redirect";
        Order: {
            /** Format: uuid */
            id: string;
            number: string;
            status: string;
            currency: string;
            lines: components["schemas"]["OrderLine"][];
            totals: components["schemas"]["OrderTotals"];
            coupon_code: string;
            buyer: components["schemas"]["Buyer"];
            shipping_address: components["schemas"]["Address"] | null;
            billing_address: components["schemas"]["BillingAddress"] | null;
            po_number: string;
            invoice_kind: string;
            payment: components["schemas"]["OrderPayment"] | null;
            invoice: components["schemas"]["InvoiceSummary"] | null;
            /** Format: date-time */
            expires_at: string | null;
            /** Format: date-time */
            placed_at: string;
            /** Format: date-time */
            paid_at: string | null;
        };
        OrderLine: {
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            product_id: string | null;
            sku: string;
            name: string;
            quantity: number;
            /** Format: decimal */
            unit_price: string;
            /** Format: decimal */
            subtotal: string;
            /** Format: decimal */
            discount: string;
            /** Format: decimal */
            net: string;
            /** Format: decimal */
            vat: string;
            /** Format: decimal */
            total: string;
        };
        OrderPayment: {
            /** Format: uuid */
            id: string;
            method: string;
            gateway: string;
            status: string;
            /** Format: decimal */
            amount: string;
            next_action: components["schemas"]["NextAction"] | null;
            failure_code: string;
            failure_message: string;
        };
        OrderTotals: {
            prices_include_vat: boolean;
            /** Format: decimal */
            vat_rate: string;
            /** Format: decimal */
            subtotal: string;
            /** Format: decimal */
            discount: string;
            /** Format: decimal */
            shipping: string;
            /** Format: decimal */
            taxable_amount: string;
            /** Format: decimal */
            vat: string;
            /** Format: decimal */
            total: string;
        };
        /**
         * @description * `applied` - applied
         *     * `duplicate` - duplicate
         *     * `ignored` - ignored
         * @enum {string}
         */
        OutcomeEnum: "applied" | "duplicate" | "ignored";
        PatchedUpdateItemRequest: {
            quantity?: number;
        };
        PaymentMethod: {
            method: string;
            gateway: string;
            display_name: string;
            requires_token: boolean;
        };
        PaymentMethodChoiceRequest: {
            method: components["schemas"]["MethodEnum"];
        };
        PaymentMethodOut: {
            method: string;
            gateway: string;
            display_name: string;
        };
        Problem: {
            type: string;
            title: string;
            status: number;
            /** @description Stable machine-readable error code. */
            code: string;
            detail?: string;
            errors?: components["schemas"]["FieldError"][];
        };
        Product: {
            /** Format: uuid */
            id: string;
            sku: string;
            name: string;
            description: string;
            kind: string;
            /**
             * Format: decimal
             * @description In the store's price basis (see GET /store).
             */
            price: string;
            in_stock: boolean;
            /** @description Units available, or null when not tracked. */
            stock_level: number | null;
            max_per_order: number;
            image_url: string;
        };
        ProductPage: {
            /**
             * Format: uri
             * @description Absolute URL of the next page, or null.
             */
            next: string | null;
            /** Format: uri */
            previous: string | null;
            results: components["schemas"]["Product"][];
        };
        ProductRef: {
            /** Format: uuid */
            id: string;
            sku: string;
            name: string;
            kind: string;
            image_url: string;
        };
        Readiness: {
            ready: boolean;
            missing: components["schemas"]["MissingEnum"][];
        };
        SignInRequest: {
            /** Format: email */
            email: string;
            password: string;
        };
        Store: {
            handle: string;
            name: string;
            currency: string;
            prices_include_vat: boolean;
            /** Format: decimal */
            vat_rate: string;
            /** Format: decimal */
            shipping_fee: string;
            /** Format: decimal */
            free_shipping_threshold: string | null;
            b2b_enabled: boolean;
        };
        Suggestion: {
            strategy: string;
            type: components["schemas"]["SuggestionTypeEnum"];
            headline: string;
            reason_code: string;
            product: components["schemas"]["Product"] | null;
            action: components["schemas"]["SuggestionAction"] | null;
            data: {
                [key: string]: unknown;
            };
        };
        SuggestionAction: {
            type: components["schemas"]["SuggestionActionTypeEnum"];
            /** Format: uuid */
            product_id: string;
            quantity: number;
        };
        /**
         * @description * `add_item` - add_item
         * @enum {string}
         */
        SuggestionActionTypeEnum: "add_item";
        SuggestionList: {
            suggestions: components["schemas"]["Suggestion"][];
        };
        /**
         * @description * `product` - product
         *     * `message` - message
         * @enum {string}
         */
        SuggestionTypeEnum: "product" | "message";
        TokenResponse: {
            token: string;
            token_type: string;
            /** Format: date-time */
            expires_at: string;
            customer: components["schemas"]["Customer"];
        };
        Totals: {
            prices_include_vat: boolean;
            /** Format: decimal */
            vat_rate: string;
            /**
             * Format: decimal
             * @description Items before discount, in the store's price basis.
             */
            subtotal: string;
            /** Format: decimal */
            discount: string;
            /**
             * Format: decimal
             * @description Shipping fee before any shipping discount.
             */
            shipping: string;
            /** Format: decimal */
            taxable_amount: string;
            /** Format: decimal */
            vat: string;
            /**
             * Format: decimal
             * @description Amount payable, including VAT.
             */
            total: string;
        };
        Warning: {
            code: string;
            detail: string;
            /** Format: uuid */
            item_id?: string;
            /** Format: decimal */
            previous_price?: string;
            /** Format: decimal */
            current_price?: string;
            reason?: string;
        };
        WebhookAck: {
            received: boolean;
            outcome: components["schemas"]["OutcomeEnum"];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    createToken: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SignInRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            /** @description Wrong email or password for this store. */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    createCart: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CreatedCart"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CreatedCart"];
                };
            };
        };
    };
    getCart: {
        parameters: {
            query?: never;
            header?: {
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                cart_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
            /** @description Cart not found, or it belongs to another customer or store. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    setBillingAddress: {
        parameters: {
            query?: never;
            header?: {
                /** @description Cart version from the last read (ETag), for example "7". A stale version returns 412. */
                "If-Match"?: string;
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                cart_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BillingAddressRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
            /** @description Cart not found, or it belongs to another customer or store. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The cart is not open, or the change conflicts with stock. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description If-Match did not match the current cart version. */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    checkoutCart: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per checkout attempt. Retrying with the same key never creates a second order. */
                "Idempotency-Key": string;
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                cart_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["CheckoutRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Order"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Order"];
                };
            };
            /** @description Cart not ready, total changed, out of stock, coupon no longer applies, or request in progress. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Payment token missing, method not allowed, or Idempotency-Key reused with another body. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Idempotency-Key header missing. */
            428: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    applyCoupon: {
        parameters: {
            query?: never;
            header?: {
                /** @description Cart version from the last read (ETag), for example "7". A stale version returns 412. */
                "If-Match"?: string;
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                cart_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApplyCouponRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
            /** @description Cart not found, or it belongs to another customer or store. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The cart is not open, or the change conflicts with stock. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description If-Match did not match the current cart version. */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Unknown coupon or a failed constraint. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    removeCoupon: {
        parameters: {
            query?: never;
            header?: {
                /** @description Cart version from the last read (ETag), for example "7". A stale version returns 412. */
                "If-Match"?: string;
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                cart_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
            /** @description Cart not found, or it belongs to another customer or store. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The cart is not open, or the change conflicts with stock. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description If-Match did not match the current cart version. */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    addCartItem: {
        parameters: {
            query?: never;
            header?: {
                /** @description Cart version from the last read (ETag), for example "7". A stale version returns 412. */
                "If-Match"?: string;
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                cart_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AddItemRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
            /** @description Cart not found, or it belongs to another customer or store. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The cart is not open, or the change conflicts with stock. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description If-Match did not match the current cart version. */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Unknown product or quantity limit. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    removeCartItem: {
        parameters: {
            query?: never;
            header?: {
                /** @description Cart version from the last read (ETag), for example "7". A stale version returns 412. */
                "If-Match"?: string;
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                cart_id: string;
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
            /** @description Cart not found, or it belongs to another customer or store. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The cart is not open, or the change conflicts with stock. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description If-Match did not match the current cart version. */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    updateCartItem: {
        parameters: {
            query?: never;
            header?: {
                /** @description Cart version from the last read (ETag), for example "7". A stale version returns 412. */
                "If-Match"?: string;
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                cart_id: string;
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedUpdateItemRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
            /** @description Cart not found, or it belongs to another customer or store. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The cart is not open, or the change conflicts with stock. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description If-Match did not match the current cart version. */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    setPaymentMethod: {
        parameters: {
            query?: never;
            header?: {
                /** @description Cart version from the last read (ETag), for example "7". A stale version returns 412. */
                "If-Match"?: string;
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                cart_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PaymentMethodChoiceRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
            /** @description Cart not found, or it belongs to another customer or store. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The cart is not open, or the change conflicts with stock. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description If-Match did not match the current cart version. */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Method not offered or not allowed for this customer. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    setShippingAddress: {
        parameters: {
            query?: never;
            header?: {
                /** @description Cart version from the last read (ETag), for example "7". A stale version returns 412. */
                "If-Match"?: string;
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                cart_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AddressRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
            /** @description Cart not found, or it belongs to another customer or store. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The cart is not open, or the change conflicts with stock. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description If-Match did not match the current cart version. */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    listCartSuggestions: {
        parameters: {
            query?: never;
            header?: {
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                cart_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SuggestionList"];
                };
            };
            /** @description Cart not found, or it belongs to another customer or store. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    getMe: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Customer"];
                };
            };
        };
    };
    listOrders: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Order"][];
                };
            };
        };
    };
    getOrder: {
        parameters: {
            query?: never;
            header?: {
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                order_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Order"];
                };
            };
            /** @description Order not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    getOrderInvoice: {
        parameters: {
            query?: {
                format?: "json" | "xml";
            };
            header?: {
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                order_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Invoice"];
                };
            };
            /** @description Order not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invoice not issued or not cleared yet. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    confirmOrderPayment: {
        parameters: {
            query?: never;
            header?: {
                /** @description Secret returned when a guest cart is created. Not needed for signed-in customers. */
                "X-Cart-Token"?: string;
            };
            path: {
                order_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Order"];
                };
            };
            /** @description Order not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    listPaymentMethods: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaymentMethod"][];
                };
            };
        };
    };
    listProducts: {
        parameters: {
            query?: {
                cursor?: string;
                kind?: "digital" | "physical" | "service";
                limit?: number;
                /** @description Search by name or SKU. */
                q?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProductPage"];
                };
            };
        };
    };
    getProduct: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                product_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Product"];
                };
            };
            /** @description Product not found in this store. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    getStore: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Store"];
                };
            };
        };
    };
    receivePaymentWebhook: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                gateway: string;
                store: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WebhookAck"];
                };
            };
            /** @description Signature invalid. */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
}
