# iter323 — SendGrid + DNS Setup Checklist (`reply.bidvex.ca`)

**You (BidVex admin)** must complete these steps **once** after the iter323 deploy, on your side. They are required for:
- contractor emails to send from `partners@bidvex.ca` without being spam-foldered, AND
- client replies to `partners+c{contractor_id}@reply.bidvex.ca` to actually reach our Inbound Parse webhook → land in the contractor's Email Hub thread + fire an in-app notification.

There are exactly **3 DNS records to add** + **2 SendGrid Dashboard actions**. ~10 minutes end-to-end.

---

## A. Sender Authentication for `bidvex.ca` (lets you send AS `partners@bidvex.ca`)

1. SendGrid Dashboard → **Settings → Sender Authentication → Authenticate Your Domain**
2. Choose your DNS host (Cloudflare / GoDaddy / etc.) when prompted.
3. Domain: `bidvex.ca`. Brand subdomain (default `em1234`) is fine.
4. SendGrid will display **3 CNAME records** in this shape:

   | Type | Host (relative to `bidvex.ca`) | Points to |
   |------|--------------------------------|-----------|
   | CNAME | `em{N}` (SendGrid picks N) | `u{XXXXXXX}.wl{NNN}.sendgrid.net` |
   | CNAME | `s1._domainkey` | `s1.domainkey.u{XXXXXXX}.wl{NNN}.sendgrid.net` |
   | CNAME | `s2._domainkey` | `s2.domainkey.u{XXXXXXX}.wl{NNN}.sendgrid.net` |

5. Add those 3 CNAMEs at your DNS host (TTL: Auto / 3600).
6. Return to SendGrid → **Verify**. Wait until SendGrid shows green check on all 3 records.

---

## B. Inbound Parse on `reply.bidvex.ca` (lets clients' replies route into our webhook)

This uses a **safer subdomain** so you don't have to touch any existing MX record on the root `bidvex.ca` domain.

7. At your DNS host, on **`bidvex.ca`** zone, add:

   | Type | Host (relative to `bidvex.ca`) | Value | Priority |
   |------|--------------------------------|-------|----------|
   | MX   | `reply` | `mx.sendgrid.net` | 10 |

   This creates `reply.bidvex.ca` as an MX-only subdomain. (Optional: add an empty `A reply` record pointing to `127.0.0.1` if your DNS requires a non-MX record for the subdomain to "exist". Most providers don't.)

8. SendGrid Dashboard → **Settings → Inbound Parse → Add Host & URL**
   - Host: `reply.bidvex.ca`
   - Destination URL: **`https://bidvex.com/api/sendgrid/inbound-parse`**
     (the `/api/sendgrid/inbound-parse` endpoint is mounted by iter323 — see `routes/contractor_ivr_inbound.py`)
   - **POST the raw, full MIME message:** unchecked (we want SendGrid's parsed form fields).
   - **Send POST grouped:** unchecked.
   - **Check incoming emails for spam:** ✅ on (recommended).
   - Save.

---

## C. Verify the chain works (smoke test)

```bash
# A. From any external mailbox (e.g. your personal Gmail), send a test email to:
#       partners+c0f45e7ca-d1f9-483b-af43-f9c6beddcef3@reply.bidvex.ca
#    (substitute the contractor_id of any active dialer_contractor)

# B. Within 30 seconds, the inbound row should appear:
curl https://bidvex.com/api/twilio/contractor/emails \
     -H "Authorization: Bearer <contractor JWT>" | jq '.items[] | select(.direction=="inbound")'

# C. The contractor's in-app bell should show a notification.
```

If the SendGrid dashboard's **Inbound Parse → Activity** log shows the message arriving but our endpoint returns non-200, check `/var/log/supervisor/backend.err.log` for `[sg-inbound]` lines — the most common cause is a missing/typo'd contractor_id in the recipient's `+c` tag.

---

## D. Caller-ID + IVR Twilio Console Action (Directive 3)

Configure the inbound voice webhook on **+1 450 634 3099** in the Twilio Console:

9. Twilio Console → **Phone Numbers → Manage → Active Numbers** → click +1 450 634 3099.
10. **Voice & Fax → A CALL COMES IN**:
    - Webhook: **`https://bidvex.com/api/twilio/ivr/incoming`** (HTTP POST)
    - Same pattern as the outbound TwiML App you already configured.
11. (Optional but recommended) **Call Status Changes** webhook can be left blank — our `<Dial action="…/api/twilio/ivr/status">` attribute already wires the per-bridge status callback.

12. Test by dialling **+1 450 634 3099** from any phone. You should hear:
    > "Thank you for calling BidVex. For English, press 1. Pour le français, appuyez sur le 2."

---

## Done. Routing pipeline is now live.

| Trigger | What happens |
|---------|-------------|
| Contractor sends an email through the Email Hub | From `partners@bidvex.ca`, Reply-To `partners+c{id}@reply.bidvex.ca`, signature ends `+1 450 634 3099 ext. 1220`. |
| Client hits **Reply** | Lands in `reply.bidvex.ca` MX → SendGrid Inbound Parse → POST our webhook → `contractor_emails` row (direction=inbound) + `notifications` row for that contractor. |
| Client dials **+1 450 634 3099** | Bilingual IVR → enters ext 1220 → Twilio bridges to contractor's personal phone (E.164). Contractor's phone shows caller-ID = BidVex main number + hears whisper: "Incoming BidVex call from +1xxxxxxxxxx. Connecting now." |
