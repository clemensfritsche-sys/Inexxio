"""Stripe-Provider – **Vollintegration** (eingebettete Kasse + Adaptive Pricing + Stripe Tax).

- ``create_checkout``: erstellt eine Stripe **Checkout Session** im Modus ``ui_mode='embedded'``
  (kein Redirect – die Kasse wird auf unserer Seite eingebettet, ``client_secret``). KEINE
  Währung gesetzt → **Adaptive Pricing** zeigt die Lokalwährung; ``automatic_tax`` →
  **Stripe Tax**. Modus ``payment`` (Einmalkauf) oder ``subscription`` (Abo). Mehrere
  Warenkorb-Positionen ⇒ mehrere ``line_items`` in EINER Session. Die Lieferadresse wird
  aus dem **Profil** auf den Stripe-Customer gespiegelt (Vorbefüllung, keine Doppeleingabe).
- ``handle_webhook``: signaturgeprüft; erzeugt/finalisiert bei bestätigter Zahlung die
  Aufträge des Intents (Defer-Modell) und friert den real bezahlten Betrag/Währung/Steuer
  je Position als Snapshot ein (Stripe = Quelle der Wahrheit).
- ``create_portal_session``: Stripe **Customer Portal** (Abo/Zahlungsmittel selbst verwalten).

Hart geschützt: ohne ``STRIPE_SECRET_KEY`` ist der Provider nie aktiv (sauberer 503, kein Crash).
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...models import CheckoutIntent, Order, Sale, UserProfile
from .. import sales as sales_svc
from ..events import emit
from .base import PaymentProvider


def _stripe():
    """Das Stripe-SDK mit gesetztem Key – oder sauberer 503, wenn nicht konfiguriert."""
    key = get_settings().stripe_secret_key
    if not key:
        raise HTTPException(
            503, detail="Stripe ist nicht konfiguriert (STRIPE_SECRET_KEY fehlt).")
    import stripe
    stripe.api_key = key
    return stripe


def _full_name(u: UserProfile) -> str | None:
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or None


def _addr(line1, line2, city, postal, state, country) -> dict | None:
    if not (line1 and city and postal and country):
        return None
    return {
        "line1": line1,
        "line2": line2 or None,
        "city": city,
        "postal_code": postal,
        "state": state or None,
        "country": (country or "CH")[:2].upper(),
    }


def _profile_shipping(u: UserProfile) -> dict | None:
    """Lieferadresse aus dem Profil als Stripe-``shipping``-Objekt (oder None)."""
    addr = _addr(u.ship_address_line1 or u.address_line1,
                 u.ship_address_line2 or u.address_line2,
                 u.ship_city or u.city, u.ship_postal_code or u.postal_code,
                 u.ship_state_region or u.state_region, u.ship_country or u.country or "CH")
    if not addr:
        return None
    return {"name": u.ship_name or _full_name(u) or u.email, "address": addr}


def _profile_billing(u: UserProfile) -> dict | None:
    """Rechnungsadresse aus dem Profil als Stripe-``address``-Objekt (Fallback: Kontaktadresse)."""
    return _addr(u.invoice_address_line1 or u.address_line1,
                 u.invoice_address_line2 or u.address_line2,
                 u.invoice_city or u.city, u.invoice_postal_code or u.postal_code,
                 u.state_region, u.invoice_country or u.country or "CH")


def _ensure_customer(db: Session, stripe, user: UserProfile) -> str:
    """Den Stripe-Customer holen/anlegen (idempotent) und **Liefer- + Rechnungsadresse aus dem
    Profil** spiegeln. Das Profil ist die **Single Source of Truth** – auf Stripe wird KEINE
    Adresse erfasst (siehe ``create_checkout``); jeder Checkout aktualisiert den Customer."""
    shipping = _profile_shipping(user)
    billing = _profile_billing(user)
    fields = {}
    if shipping:
        fields["shipping"] = shipping
    if billing:
        fields["address"] = billing
    if user.stripe_customer_id:
        if fields:
            try:
                stripe.Customer.modify(user.stripe_customer_id, **fields)
            except Exception:
                pass
        return user.stripe_customer_id
    cust = stripe.Customer.create(
        email=user.email, name=_full_name(user),
        metadata={"user_id": user.id, "object_id": user.object_id or ""}, **fields,
    )
    user.stripe_customer_id = cust.id
    db.commit()
    return cust.id


class StripeProvider(PaymentProvider):
    name = "stripe"

    # ─── Checkout ────────────────────────────────────────────────────────────────
    def create_checkout(self, db: Session, intent: CheckoutIntent,
                        customer: UserProfile) -> dict:
        stripe = _stripe()
        settings = get_settings()
        lines = list(intent.lines or [])
        if not lines:
            raise HTTPException(400, detail="Warenkorb ist leer")
        customer_id = _ensure_customer(db, stripe, customer)
        tax_behavior = "inclusive" if settings.prices_tax_inclusive else "exclusive"
        is_sub = any(l.get("kind") == "subscription" for l in lines)

        line_items = [self._line_item(line, tax_behavior) for line in lines]
        meta = {"intent_id": str(intent.id)}
        params = {
            "ui_mode": "embedded",
            "mode": "subscription" if is_sub else "payment",
            "customer": customer_id,
            "line_items": line_items,
            # Stripe Tax nur, wenn im Dashboard eingerichtet (sonst schlägt die Session fehl).
            "automatic_tax": {"enabled": bool(settings.stripe_tax_enabled)},
            # Single Source of Truth = Profil: KEINE Adress-Erfassung auf Stripe. Liefer- und
            # Rechnungsadresse kommen aus dem Customer (aus dem Profil gespiegelt, s. _ensure_customer).
            "billing_address_collection": "auto",
            "metadata": meta,
            # Eingebettete Kasse: KEIN Redirect – der Abschluss wird inline (onComplete) in
            # unserer Kasse angezeigt (kein separates Erfolgs-Fenster, kein Abbruch-Hänger).
            "redirect_on_completion": "never",
            # KEINE currency → Adaptive Pricing wählt die Lokalwährung des Kunden.
        }
        if is_sub:
            params["subscription_data"] = {"metadata": meta}
        else:
            params["payment_intent_data"] = {"metadata": meta}

        session = stripe.checkout.Session.create(**params)
        intent.stripe_session_id = session.id
        db.commit()
        return {"provider": self.name, "session_id": session.id,
                "client_secret": session.client_secret, "payment_url": None}

    def _line_item(self, line: dict, tax_behavior: str) -> dict:
        qty = int(line.get("quantity") or 1)
        base = Decimal(str(line.get("base_amount_chf") or 0))
        unit = (base / qty) if qty else base
        price_data = {
            "currency": "chf",                  # Basis – Adaptive Pricing rechnet lokal um
            "unit_amount": int((unit * 100).quantize(Decimal("1"))),
            "tax_behavior": tax_behavior,
            "product_data": {
                "name": line.get("article_name") or "Produkt",
                "tax_code": get_settings().stripe_default_tax_code,
                "metadata": {"article_object_id": line.get("article_object_id") or ""},
            },
        }
        if line.get("kind") == "subscription":
            price_data["recurring"] = {
                "interval": "year" if line.get("interval") == "year" else "month"}
        return {"price_data": price_data, "quantity": qty}

    # ─── Webhook ─────────────────────────────────────────────────────────────────
    def handle_webhook(self, db: Session, raw: bytes, sig: str | None,
                       payload: dict | None) -> CheckoutIntent | None:
        stripe = _stripe()
        secret = get_settings().stripe_webhook_secret
        # FIX: Ohne Webhook-Secret wurden Events unverifiziert verarbeitet (nur eine
        # Log-Warnung) – ein gefälschtes checkout.session.completed hätte Erfüllung ohne
        # Zahlung ausgelöst. Fehlkonfiguration muss hart scheitern statt still durchwinken.
        if not secret:
            raise HTTPException(
                503, detail="Stripe-Webhook ist nicht konfiguriert (STRIPE_WEBHOOK_SECRET fehlt).")
        try:
            event = stripe.Webhook.construct_event(raw, sig, secret)
        except Exception as e:  # ungültige Signatur → 400 (Stripe wiederholt nicht endlos)
            raise HTTPException(400, detail=f"Ungültige Webhook-Signatur: {e}")

        etype = event["type"] if isinstance(event, dict) else event.type
        obj = (event["data"]["object"] if isinstance(event, dict) else event.data.object)

        if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            return self._on_completed(db, stripe, obj)
        if etype in ("checkout.session.expired", "checkout.session.async_payment_failed"):
            return self._on_failed(db, obj)
        if etype == "customer.subscription.deleted":
            return self._on_subscription_ended(db, obj)
        if etype == "invoice.paid":
            return self._on_invoice_paid(db, obj)
        return None

    # ─── Event-Handler ───────────────────────────────────────────────────────────
    def _resolve_intent(self, db: Session, session) -> CheckoutIntent | None:
        iid = (_get(session, "metadata") or {}).get("intent_id")
        if iid:
            it = db.query(CheckoutIntent).filter(CheckoutIntent.id == int(iid)).first()
            if it:
                return it
        sid = _get(session, "id")
        return db.query(CheckoutIntent).filter(
            CheckoutIntent.stripe_session_id == sid).first() if sid else None

    def _on_completed(self, db: Session, stripe, session) -> CheckoutIntent | None:
        status = _get(session, "payment_status")
        if status not in ("paid", "no_payment_required", None):
            return None   # asynchrone Methode noch offen → async_payment_succeeded abwarten
        intent = self._resolve_intent(db, session)
        if not intent:
            return None
        snap = self._snapshot(stripe, session)
        sales_svc.fulfill_intent(db, intent, snapshot=snap)
        return intent

    def _on_failed(self, db: Session, session) -> CheckoutIntent | None:
        intent = self._resolve_intent(db, session)
        if intent:
            sales_svc.cancel_intent(db, intent)
        return intent

    def _on_subscription_ended(self, db: Session, sub) -> CheckoutIntent | None:
        sub_id = _get(sub, "id")
        order = db.query(Order).filter(Order.stripe_subscription_id == sub_id).first()
        # FIX: Nach dem Abschluss des Abo-Auftrags trägt ein Folge-Entwurf die Wiederkehr
        # (recurrence_active am Original = False) – der alte Guard tat dann NICHTS und die
        # lokale Kette spawnte weiter, obwohl Stripe das Abo beendet hatte.
        if order and sales_svc.deactivate_recurrence_chain(db, order):
            emit(db, "subscription.cancelled", object_type="order", object_id=order.object_id)
            db.commit()
        return None

    def _on_invoice_paid(self, db: Session, invoice) -> CheckoutIntent | None:
        """Wiederkehrende Verrechnung läuft in Stripe (Quelle der Wahrheit) – wir spiegeln.

        **Produktabo (kind='product'): Auto-Fulfillment je Zyklus.** ``_spawn_recurrence``
        legt beim Abschluss eines Zyklus den Folge-Auftrag als **Entwurf** an (mit kopiertem
        Ablauf: Verkauf + Pflicht-Versand). Die bezahlte Abo-Rechnung gibt diesen Entwurf
        frei und verbucht seinen Verkauf als bezahlt – die Ware geht wie gewohnt über den
        Versand-Schritt raus. Idempotent: die Erst-Rechnung (Zyklus 1) trifft den bereits
        bezahlten Original-Auftrag (kein Entwurf am Kettenende → nichts zu tun), Webhook-
        Retries treffen einen bereits freigegebenen Folge-Auftrag. Ist der VORHERIGE Zyklus
        noch nicht abgeschlossen (noch kein Entwurf gespawnt), wird nur das Event vermerkt –
        der Abschluss des Vorgängers zieht den Folge-Auftrag nach (nächster Zyklus greift).
        Beim **Nutzungsabo** (Zugang/Miete) ist nichts zu liefern."""
        sub_id = _get(invoice, "subscription")
        order = (db.query(Order).filter(Order.stripe_subscription_id == sub_id).first()
                 if sub_id else None)
        kind = order.recurrence_kind if order else None
        fulfilled_object_id = None
        if order is not None and kind == "product":
            from .. import sale as sale_svc, supply
            from ..orders import release_order
            chain = sales_svc.recurrence_chain(db, order)
            current = chain[-1] if chain else None
            if (current is not None and current.status == "draft"
                    and current.recurrence_active):
                release_order(db, current, None)             # Ablauf starten (Verkauf+Versand)
                supply.ensure_supply(db, current, None)      # Fehlmenge → Nachschub (make-Artikel)
                db.flush()
                for s in db.query(Sale).filter(Sale.order_id == current.id,
                                               Sale.is_active == True).all():
                    sale_svc.finalize_paid(db, s, stripe=None, release_order=False)
                fulfilled_object_id = current.object_id
        emit(db, "stripe.invoice_paid", object_type="order",
             object_id=order.object_id if order else None,
             payload={"subscription": sub_id, "recurrence_kind": kind,
                      "fulfilled_order": fulfilled_object_id})
        db.commit()
        return None

    def _snapshot(self, stripe, session) -> dict:
        """Real bezahlten Betrag/Währung/Steuer aus der Session lesen (Settlement = CHF;
        Adaptive-Pricing-Lokalwährung via ``presentment_details``)."""
        total = Decimal(str(_get(session, "amount_total") or 0)) / 100
        td = _get(session, "total_details") or {}
        tax = Decimal(str((td.get("amount_tax") if isinstance(td, dict) else _get(td, "amount_tax")) or 0)) / 100
        net = total - tax
        cur = (_get(session, "currency") or "chf").upper()
        pres = _get(session, "presentment_details") or {}
        presentment = {}
        if pres:
            presentment = {
                "currency": (_get(pres, "presentment_currency") or "").upper() or None,
                "total": _money(_get(pres, "presentment_amount")),
            }
        return {
            "settlement": {"currency": cur, "total": _q(total), "tax": _q(tax)},
            "presentment": presentment,
            "payment_intent": _get(session, "payment_intent"),
            "subscription": _get(session, "subscription"),
            "mode": _get(session, "mode"),
            "tax_rate": str((tax / net * 100).quantize(Decimal("0.01"))) if net > 0 else "0",
        }

    # ─── Abo kündigen (on-site) ──────────────────────────────────────────────────
    def cancel_subscription(self, db: Session, order) -> bool:
        """Das Stripe-Abo **sofort** kündigen, dann lokal spiegeln. Schlägt der Stripe-Call
        fehl, wird NICHT lokal gekündigt (sauberer Fehler) – der Kunde sieht das Abo weiter
        aktiv und kann erneut kündigen, statt dass es im Hintergrund weiterläuft."""
        sub_id = getattr(order, "stripe_subscription_id", None)
        if sub_id:
            stripe = _stripe()
            try:
                stripe.Subscription.cancel(sub_id)
            except Exception as e:
                # Bereits gekündigt? → als Erfolg behandeln; sonst sauberer Fehler.
                msg = str(e).lower()
                if "no such subscription" not in msg and "canceled" not in msg:
                    raise HTTPException(502, detail=f"Kündigung bei Stripe fehlgeschlagen: {e}")
        # FIX: Nach Auftrags-Abschluss trägt ein Folge-Entwurf die Wiederkehr
        # (_spawn_recurrence) – die ganze Kette beenden, nicht nur das Original.
        if sales_svc.deactivate_recurrence_chain(db, order):
            emit(db, "subscription.cancelled", object_type="order", object_id=order.object_id)
        db.commit()
        return True

    # ─── Gutschrift erstatten (Refund) ───────────────────────────────────────────
    def refund(self, db: Session, original_sale, credit_sale) -> dict | None:
        """Refund gegen den **Original-PaymentIntent** – anteilig auf Basis der **Position**.

        Grundlage ist der beim Kauf eingefrorene **Positions-Brutto** (Snapshot
        ``settlement.total`` – bei einem Mehrpositionen-Warenkorb der anteilige Betrag
        DIESER Position, ``sales._split_snapshot``), skaliert mit dem Gutschrift-Anteil
        (netto Gutschrift ÷ netto Original, Teil-Erstattung/Kulanz). Ohne Original-
        PaymentIntent (Direkt-/Rechnungsverkauf) → ``None`` (offline abzuwickeln)."""
        pi_id = getattr(original_sale, "stripe_payment_intent_id", None) if original_sale else None
        if not pi_id:
            return None
        stripe = _stripe()
        params: dict = {"payment_intent": pi_id}
        o_net = getattr(original_sale, "order_total", None)
        c_net = getattr(credit_sale, "order_total", None)
        frac = Decimal("1")
        if o_net and c_net and Decimal(str(c_net)) < Decimal(str(o_net)):
            frac = Decimal(str(c_net)) / Decimal(str(o_net))
        snap = getattr(original_sale, "stripe_snapshot", None) or {}
        line_gross = Decimal(str((snap.get("settlement") or {}).get("total") or 0))
        try:
            # FIX: Vorher wurde bei voller Positions-Gutschrift der GANZE PaymentIntent
            # erstattet (kein amount) bzw. anteilig auf den GANZEN Warenkorb gerechnet –
            # die Rückgabe EINER Position eines Mehrpositionen-Kaufs erstattete so den
            # gesamten Kaufbetrag. Jetzt: Positions-Brutto × Anteil, in Rappen der
            # PI-Währung; ohne amount (= voller Refund) nur, wenn die Position die ganze
            # Zahlung deckt.
            pi = stripe.PaymentIntent.retrieve(pi_id)
            charged = int(_get(pi, "amount") or 0)
            if line_gross > 0:
                amount = int((line_gross * 100 * frac).to_integral_value())
            else:
                # Alt-Beleg ohne Snapshot: der Anteil lässt sich nur am GANZEN PaymentIntent
                # rechnen. Bei einem Mehrpositionen-Kauf würde die volle Gutschrift EINER
                # Position so den gesamten Kaufbetrag erstatten (Überzahlung) → ablehnen und
                # auf die manuelle Erstattung im Stripe-Dashboard verweisen.
                sibling = (
                    db.query(Sale.id)
                    .filter(Sale.order_id == original_sale.order_id, Sale.kind == "sale",
                            Sale.id != original_sale.id, Sale.is_active == True)
                    .first()
                )
                if sibling is not None:
                    raise HTTPException(
                        409,
                        detail="Alt-Beleg ohne Positions-Snapshot bei Mehrpositionen-Kauf – der "
                               "anteilige Betrag ist nicht sicher bestimmbar. Bitte die Erstattung "
                               "manuell im Stripe-Dashboard ausführen.",
                    )
                amount = int((Decimal(charged) * frac).to_integral_value())
            if 0 < amount < charged:
                params["amount"] = amount
            r = stripe.Refund.create(**params)
        except Exception as e:
            raise HTTPException(502, detail=f"Rückerstattung bei Stripe fehlgeschlagen: {e}")
        return {
            "refund_id": _get(r, "id"),
            "payment_method": "stripe",
            "snapshot": {"amount": _get(r, "amount"), "currency": _get(r, "currency"), "status": _get(r, "status")},
        }

    # ─── Customer Portal ─────────────────────────────────────────────────────────
    def create_portal_session(self, db: Session, user: UserProfile, return_url: str) -> str | None:
        stripe = _stripe()
        if not user.stripe_customer_id:
            raise HTTPException(404, detail="Kein Stripe-Kunde – noch kein Kauf getätigt")
        ps = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id, return_url=return_url)
        return ps.url


# ─── Helfer (tolerant ggü. dict ODER Stripe-Objekt) ──────────────────────────────

def _get(obj, key):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _money(v) -> str | None:
    if v is None:
        return None
    return str((Decimal(str(v)) / 100).quantize(Decimal("0.01")))


def _q(v: Decimal) -> str:
    return str(v.quantize(Decimal("0.01")))
