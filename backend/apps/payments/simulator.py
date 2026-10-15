import json
import secrets

import requests
from celery import shared_task
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .gateways.fakepay import SIGNATURE_HEADER, sign_payload
from .models import SimulatedCharge


@shared_task(bind=True, max_retries=5, default_retry_delay=5)
def deliver_fakepay_webhook(self, charge_id):
    charge = SimulatedCharge.objects.get(pk=charge_id)
    body = json.dumps(
        {
            "id": f"evt_{secrets.token_hex(8)}",
            "type": f"charge.{charge.status}",
            "data": {
                "charge_id": charge.pk,
                "reference": charge.reference,
                "status": charge.status,
                "failure_code": charge.failure_code,
            },
        }
    ).encode()
    try:
        response = requests.post(
            charge.webhook_url,
            data=body,
            headers={"Content-Type": "application/json", SIGNATURE_HEADER: sign_payload(charge.store_id, body)},
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise self.retry(exc=exc) from exc
    return response.status_code


@csrf_exempt
@require_http_methods(["GET", "POST"])
def three_d_secure(request, charge_id):
    charge = SimulatedCharge.objects.filter(pk=charge_id).first()
    if charge is None:
        raise Http404
    if request.method == "GET":
        return render(request, "payments/fakepay_3ds.html", {"charge": charge})
    if charge.status == SimulatedCharge.Status.REQUIRES_ACTION:
        approved = request.POST.get("outcome") == "approve"
        updated = SimulatedCharge.objects.filter(pk=charge.pk, status=SimulatedCharge.Status.REQUIRES_ACTION).update(
            status=SimulatedCharge.Status.SUCCEEDED if approved else SimulatedCharge.Status.FAILED,
            failure_code="" if approved else "authentication_failed",
        )
        if updated:
            deliver_fakepay_webhook.delay(charge.pk)
    return HttpResponseRedirect(charge.return_url)
