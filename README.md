<div align="center">

<img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/Django-5.2-092E20?style=flat-square&logo=django&logoColor=white"/>
<img src="https://img.shields.io/badge/DRF-3.15-ff1709?style=flat-square"/>
<img src="https://img.shields.io/badge/Konnect-Sandbox-00C896?style=flat-square"/>
<img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white"/>
<img src="https://img.shields.io/badge/JWT-Auth-000000?style=flat-square"/>
<img src="https://img.shields.io/badge/OpenAPI-3.0-6BA539?style=flat-square&logo=swagger&logoColor=white"/>

# TrustFlow : Agentic Payment Verification API

**Proximity-gated payments for peer-to-peer commerce.**

</div>

---

## The Problem It Solves

> *You’ve closed a deal on Facebook Marketplace. Instead of navigating unknown streets with cash and risking theft or robbery, TrustFlow secures the exchange. We verify the presence of both parties and guarantee the payment; eliminating cash exposure and prioritizing your safety.*

When peer-to-peer commerce happens in cash, with strangers, the risks are multiple:

- **Wasted journeys.** Sellers drive across the city for buyers who ghost them.
- **Cash exposure.** Carrying large amounts of money to meet a stranger is a robbery risk.
- **Zero trust.** No mechanism to know the buyer has the funds before you hand over the goods.
- **No logging.** Once the cash changes hands , there is no audit trail.

**TrustFlow** was built to solve this. It is an autonomous, agentic payment system that makes a peer-to-peer transaction safe by verifying that both parties are physically present in the same location before a single millime moves — and then routing the funds through Konnect payment gateway, so neither party ever handles raw cash.


---

## How It Works — The Agentic Handshake


<img width="561" height="741" alt="DIAGRAM drawio" src="https://github.com/user-attachments/assets/ef495ee0-cef7-47d0-a6db-3dc9f951a523" />




The agent acts as an autonomous referee:
1. It receives the coordinates of both parties.
2. It calculates physical distance and blocks if they are not co-located.
3. On proximity confirmation, it creates the transaction record and fires a Konnect payment initiation in one atomic step.
4. When Konnect reports payment completion, it verifies via a second API call before releasing the transaction ( no single point of trust.

Every decision — block or release — is written to an `AgentAudit` log

---

## Architecture

<img width="550" height="591" alt="diagram-Page-3 drawio (2)" src="https://github.com/user-attachments/assets/722372e9-2260-4892-9cfb-f3f1329b8b57" />


## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.11 |
| Framework | Django 5.2 + Django REST Framework 3.15 |
| Authentication | SimpleJWT (Bearer token, 1-day access / 7-day refresh) |
| API Documentation | drf-spectacular (OpenAPI 3.0 + Swagger UI) |
| Payment Gateway | Konnect Network (sandbox) |
| Containerization | Docker + Docker Compose |

---

## Project Structure

```
trustflow/
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env                          ← (not committed — see .env.example)
│
├── trustflow_core/               ← Django project config
│   ├── settings.py
│   ├── urls.py                   ← Root URL conf + Swagger routes
│   ├── wsgi.py
│   └── asgi.py
│
└── api/                          ← Core application
    ├── models.py                 ← Transaction, AgentAudit
    ├── serializers.py            ← Input validation + Swagger schemas
    ├── views.py                  ← AgentVerifyView, KonnectWebhookView
    ├── urls.py                   ← /agent/verify/, /webhooks/konnect/
    ├── konnect_client.py         ← Konnect API wrapper (3 methods)
    ├── apps.py
    ├── tests.py                  ← 6 test cases (mocked Konnect)
    └── migrations/
        └── 0001_initial.py
```

---

## API Reference

### Authentication

All protected endpoints require a JWT Bearer token.

```
POST /api/auth/token/
Content-Type: application/json

{ "username": "admin", "password": "adminpass" }
```

Response:
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

Pass the access token in subsequent requests:
```
Authorization: Bearer eyJ...
```

---

### POST `/api/agent/verify/`

Verifies proximity and — if parties are co-located —  creates a transaction and initiates a Konnect payment.

Requires: `Authorization: Bearer <token>`

**Request body:**
```json
{
  "amount": 150.000,
  "lat_b": 36.8001,
  "lon_b": 10.1801,
  "lat_s": 36.8002,
  "lon_s": 10.1802
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `amount` | decimal | ✓ | Transaction amount in TND |
| `lat_b` / `lon_b` | float | ✓ | Buyer GPS coordinates |
| `lat_s` / `lon_s` | float | ✓ | Seller GPS coordinates |

**Success response (200):**
```json
{
  "decision": "SUCCESS",
  "pay_url": "https://pay.sandbox.konnect.network/...",
  "payment_ref": "sandbox_tx_abc123"
}
```

**Blocked response (403):**
```json
{
  "decision": "BLOCKED",
  "reason": "Proximity failed. Parties are too far apart."
}
```

---

### GET `/api/webhooks/konnect/`

**Triggered automatically by Konnect servers** when a payment is processed.



**Responses:**
```json
{ "status": "verified" }   ← payment confirmed, transaction RELEASED
{ "status": "ignored" }    ← payment not complete, no state change
```
---

## Transaction Lifecycle

```
SECURED  ──[AgentVerify: proximity OK + Konnect initiated]──▶  PENDING
PENDING  ──[Webhook + API cross-verify: completed]───────────▶  RELEASED
PENDING  ──[Webhook/API mismatch or failure]─────────────────▶  (stays PENDING, audit logged)
```

---

## Environment Variables

Create a `.env` file at the project root:

```env
# --- DJANGO SETTINGS ---
DEBUG=True
DJANGO_SECRET_KEY=cle_secrete

# --- KONNECT SETTINGS (Sandbox) ---
KONNECT_API_KEY= cle_api_konnect
KONNECT_WALLET_ID= wallet_id


ALLOWED_HOSTS=localhost 127.0.0.1
KONNECT_WEBHOOK_URL=https://trustflow.tn/api/webhooks/konnect/
DB_PATH=/app/data/db.sqlite3
```

---

## Running Locally

### Prerequisites

- Docker 

### With Docker (recommended)

```bash
git clone [repo_link]
cd veriflow

git checkout develop
docker compose up --build
```

The container automatically:
- Runs all database migrations
- Creates a superuser (no manual step needed)

**Default credentials:**
| Field | Value |
|---|---|
| Username | `admin` |
| Password | `adminpass` |

Use these to authenticate at `POST /api/auth/token/` and get your JWT token.

The container automatically runs migrations, creates the database, and starts Gunicorn. 


Once running, open:

```
http://127.0.0.1:8000/api/docs/
```

To authenticate in Swagger:
1. `POST /api/auth/token/` → copy the `access` value
2. Click **Authorize** (top right)
3. Enter `Bearer <access_token>`
4. All protected endpoints are now unlocked

---






## Running Tests

The test suite runs entirely inside Docker — no local Python setup needed.

**Step 1 — Start the containers (if not already running):**
```bash
docker compose up --build -d
```

**Step 2 — Run the test suite:**
```bash
docker compose exec web python manage.py test api -v 2
```


The test suite (6 cases) covers:

| Test | What it verifies |
|---|---|
| `test_successful_handshake` | Proximity pass → transaction created → Konnect initiated |
| `test_blocked_by_proximity` | Distance > 100m → 403 + audit written |
| `test_unauthenticated_request_returns_401` | No JWT → 401 |
| `test_konnect_failure_returns_500` | Konnect API down → 500, TX unchanged |
| `test_completed_webhook_releases_transaction` | Full webhook + API verify → RELEASED |
| `test_pending_webhook_is_ignored` | Non-completed webhook → no state change |


---

## Security Notes

- JWT access tokens expire after **1 day**; refresh tokens after **7 days**
- Every agent decision — including blocks and failures — is persisted in `AgentAudit` before returning a response
- Konnect payment confirmation requires **both** a webhook signal and an independent API verification call

---

## Roadmap

- [ ] Haversine-based GPS distance (replaces Euclidean approximation)
- [ ] SMS notification to seller on payment completion
- [ ] Admin dashboard with transaction and audit log views
- [ ] Rate limiting on the verify endpoint

---

## License

MIT License. See `LICENSE` for details.

---

<div align="center">
Built with passion for the fintech ecosystem 💙
</div>


