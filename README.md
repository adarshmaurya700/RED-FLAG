# red flag.

**Know before you consume.** An evidence-first early-warning workspace for Indian food, beverage and supplement safety.

Catch the difference between a bad factory batch, a sketchy seller and a local cold-chain failure. Inspect the receipts. Export a reviewable next step.

## Start here

Requires Docker Desktop with Compose. No external API keys are needed.

```sh
docker compose up --build
```

Open [the radar](http://localhost:3000) and [API documentation](http://localhost:8000/docs). PostgreSQL and Redis stay on the private Compose network. The two app ports bind to localhost. Stop with `docker compose down`; data remains in named volumes.

On Windows, run `./run_demo.ps1`. On macOS/Linux, run `sh ./run_demo.sh`.

### Native demo without Docker

Install [uv](https://docs.astral.sh/uv/) and [Node.js 24 LTS](https://nodejs.org/). Then:

```powershell
.\run_demo.ps1 -Native
```

```sh
sh ./run_demo.sh --native
```

The native demo uses SQLite and asynchronous in-process jobs. Production requires PostgreSQL, Redis and Celery; the local task runner is for a single process. First installation needs internet for packages. Seeded runtime operation does not require internet or model downloads. Live scans require network access.

## Three kinds of evidence

- **Real reports:** searchable, dated source profiles for Priyagold's October 2026 bran/recall reporting, Delhi's 2026 expiry-date operation, and the historical 2024 MDH/Everest spice recalls. Search `pari case`, `Priyagold`, `husk`, `Delhi expiry`, or `MDH`. Original notices and reporting are linked. The Hindu article supplied by the operator is included with a publisher-access note. These profiles have no invented risk scores and do not imply current nationwide recalls.
- **Synthetic scenarios:** the three requested fictional investigations, explicitly marked DEMO. Their assessed factors produce scores **88, 79 and 74**, with attribution **85/10/5**, **8/87/5** and **6/4/90**. Case 03 has 28 individual synthetic complaints split across two separate 2.5 km nodes. The other cases show representative evidence alongside supplied aggregate scenario counts. Fictional brands and contacts are not real allegations.
- **Live scans:** public records collected on demand, source outcomes, extraction provenance, a provisional assessment and a persistent case. No results remain no results. Blocked sources are never replaced with fake evidence.

The supplied license `10012021000518` is a synthetic linkage key, not a verified claim about a real license holder. Synthetic graph links and source-free demo cards are labeled accordingly.

## Trustified and Food Pharmer daily scanner

The **Tested & reviewed** section searches publisher findings with source,
outcome, tested batch, original dates, review method and proof links. Trustified
pass/fail and NMR pages and Food Pharmer category/product pages are collected
using public HTML. Recommendations, reported tests and expired testing statuses
remain distinct. Findings do not change investigation scores or create complaint
evidence, regulatory records or action packets.

`Daily source scanner` runs on a standard GitHub Actions Linux runner at
**06:17 IST** (`47 0 * * *` UTC), with **Run workflow** for manual retries.
Schedules are best effort; GitHub can delay jobs or disable schedules in inactive
public repositories. No model API, paid crawler or always-on server is needed.
Only the publisher job has `contents: write`; it commits the validated catalogue
to `codex/source-data` with the built-in Actions token. Workflow artifacts are
retained for one day.

The backend and hosted demo read that fixed public branch with hourly caching.
Vercel validates before caching and falls back to its bundled catalogue when the
published version is unavailable. Daily changes need no redeployment. Backend
fetch failures retain previously validated data. Records older than 48 hours
show as stale. Partial coverage and pending pages remain visible.

The scanner respects robots.txt, identifies itself, requests at most one page
per second per host, and limits runs to 600 requests and 20 minutes. Pending
pages resume before checked pages. Some older Trustified links return empty
public templates or errors; these remain unreadable rather than interpreted.
The scanner does not log in or use hidden APIs.

Run `backend/.venv/Scripts/python.exe scripts/scan_sources.py` locally.
Add `--from-published` to resume the data branch, or `--output <path>` to choose
an output file. Copy the result to `frontend/src/data/source-catalog.json` before
building to refresh the bundled fallback.

`GET /api/v1/source-findings?q=MDH&source=trustified&outcome=fail&offset=0&limit=20`
uses existing authentication. Sources: `all`, `trustified`, `foodpharmer`.
Outcomes: `all`, `pass`, `fail`, `recommended`, `expired`, `unknown`.
The response includes `items`, `total`, source health, timestamps and catalogue
origin. Full-app scans accept both new source names and return matching reviews
in `results.source_findings`, separately from `case_ids`.

## Live scan and optional providers

The default scan queries Reddit public `search.json` and Google News RSS with `httpx`. The initial feasibility check returned Google RSS HTTP 200 and Reddit HTTP 403. Hosted Reddit access generally requires approved OAuth access; optionally set `REDDIT_ACCESS_TOKEN`. A partial scan still retains successful sources.

Copy `.env.example` to `.env` for optional integrations. No secret belongs in `NEXT_PUBLIC_*` variables or Git.

- `TINYFISH_API_KEY`: opt-in read-only public-page collection from supported product URLs. The UI exposes enhanced collection when configured.
- `BRIGHTDATA_API_KEY` and `BRIGHTDATA_DATASET_IDS`: a JSON map of marketplace hostname to the dataset ID enabled in your account. Select `brightdata` through the scan API with product URLs.
- `GEMINI_API_KEY`, `GEMINI_MODEL`: structured, extractive enrichment. The default is the requested `gemini-2.5-flash`; its provider availability changes in December 2026. Configure an available model for your account. Provider failure falls back to labeled deterministic extraction. The first eight relevant records are eligible for enrichment to bound provider cost and latency. Gemini does not assign final risk or clinical severity.
- `SARVAM_API_KEY`: audio transcription using `saaras:v3`.
- `BHASHINI_API_KEY`, `BHASHINI_USER_ID`, `BHASHINI_PIPELINE_ID`: configuration/inference adapter; service access and production agreements are account-dependent.
- `NLP_MODE=transformers`: optional local HingRoBERTa and IndicBERT v2 encoders. Provision weights separately and install `backend/requirements-ml.txt`. `COMET_MODEL` enables local sequence generation. Inferred hypotheses do not establish symptoms or causality.
- `GRAPH_BACKEND=cognee`: mirror sanitized graph data to installed Cognee. PostgreSQL remains the durable record if that optional service is unavailable.

## How an assessment works

The baseline uses regulatory, adverse-event, web and credibility factors in weights **0.20 / 0.25 / 0.35 / 0.20**. The agreed continuous amplification is:

```python
base_score = .20*S_reg + .25*S_ae + .35*S_web + .20*S_cred
pre_recall_factor = max(0.0, 1.0 - S_reg/100.0)
phi = 1.0 + .25*pre_recall_factor*(S_web*S_cred/10000.0) * (1.0 + .50*velocity)
risk = min(100.0, round(phi*base_score, 1))
```

Seed velocities are **0.56 / 0.93 / 0.40**. Live velocity is `clamp((current48h - previous48h) / max(previous48h, 1), 0, 1)`. Missing historical coverage means zero growth and an explicit missing-baseline flag. News articles do not count as consumer complaints.

The versioned live rubric uses maximum matched regulatory action severity, maximum extracted clinical severity with reported temporal cues, bounded complaint volume and growth, and source diversity/verified-purchase/lab evidence. Its constants and contributions are inspectable in `risk_scorer.py`. It is an engineering triage heuristic, not a medically validated prediction.

The tri-vector classifier normalizes heuristic attribution weights. Missing or ambiguous evidence requires review. Shared manufacturer license/supplier links are persisted as graph edges; a PIN prefix does not establish an exact geographic radius.

RECAM-related fields are extracted reported cues. The app does not calculate a validated RECAM/RUCAM clinical causality assessment or infer illness from negative sentiment alone.

## Action desk and clocks

At risk ≥70 with clear attribution, generate immutable draft packet versions:

- Factory: Schedule I food recall information and urgent consumer notice.
- Counterfeit: seller investigation/takedown request, authentication advisory and lab request.
- Dark store: separate node-specific stock quarantine and cold-chain audit advisory.

PDF/JSON exports carry explicit draft and synthetic labels. Missing business/batch details remain missing; the app does not invent them. No email, regulator submission, marketplace enforcement or public notice is sent.

Record a recall decision to start the initial **24-hour notification** and **weekly status** clocks. Record an actual authority query receipt to start its separate **24-hour response** clock. Record externally submitted weekly status reports and recovered/distributed quantities. Food Safety Connect grievance records track the **15-day forwarding milestone**; the **48-hour priority** is internal policy. Celery Beat flags due grievances without claiming that an external escalation was submitted.

## Regulatory imports

`POST /api/v1/regulatory/import?source=foscos&format=json` accepts a multipart `file`. Sources are `foscos`, `pvpi`, `ayush`, `food_safety_connect`, `nch`, and `bis`. Add `case_id` to attach a record to a live case. Live imports cannot modify demonstration cases.

JSON/CSV and structured HTML tables are supported. PDF import extracts labeled key/value fields where available; unstructured/scanned documents require manual transcription into the schema rather than fabricated parsing. Imports validate the entire document before persistence.

Example JSON:

```json
[{"fbo_name":"Example business","fssai_license_no":"10012021000518","brand_name":"Example brand","food_category_code":"12","action_type":"Improvement Notice","reason_for_recall":"Describe the actual official record","start_date":"2026-11-01T00:00:00Z"}]
```

Licenses must be 14-digit strings. Categories `01`–`18`, `99`, `100`, `101`, `102` are accepted. License type is explicit; shape validation is not registry verification. Public regulator pages and manually imported records are supported without claiming unrestricted API access to private vigilance databases.

## API quick reference

- `GET /health`, `GET /ready`
- `GET /api/v1/telemetry`, `/cases`, `/cases/{id}`, `/cases/{id}/evidence`, `/cases/{id}/graph`
- `GET /api/v1/reference-cases?q=pari%20case`, `/reference-cases/{id}`
- `POST /api/v1/scans`; poll `GET /api/v1/scans/{id}`
- `POST /api/v1/cases/{id}/packets`; `GET /api/v1/packets/{id}?format=pdf|json`
- `PATCH /api/v1/grievances/{id}`
- `POST /api/v1/cases/{id}/recall-decision`, `/authority-queries`, `/weekly-status`
- `POST /api/v1/regulatory/import`, `/audio/transcribe`

Scan bodies accept `product_name`, optional `brand`, optional `product_urls`, and sources (`reddit`, `google_news`, `tinyfish`, `brightdata`). An `Idempotency-Key` replays the same job; conflicting reuse returns 409. Jobs end in `completed`, `partial` or `failed`. A five-minute cache reduces repeated scans.

## Privacy and access

Consumer text is scrubbed before persistence and downstream text-model processing. Known identity fields are discarded; regex recognizes contact details, handles, common address patterns and explicit personal-name introductions. URLs lose tracking parameters and personal profile paths. Audio is transcribed in-memory by the selected provider only after the caller supplies a processing basis; raw audio is not stored in the database or queue.

Automated redaction has limits and is not a DPDPA certification. Public availability alone is not treated as a blanket legal exemption. Authorized business recall contacts are separate from scraped consumer identities. Precise consumer addresses and voice-biometric profiles are not retained.

The hosted Next.js gateway uses HTTP Basic auth with username **operator** and `HOSTED_OPERATOR_PASSWORD`. Production refuses to run the gateway without a password. FastAPI is a private Render service authenticated by `INTERNAL_API_KEY`; PostgreSQL and Redis have no public allow-list. Same-origin checks protect browser writes. Keep the operator password strong and keep native demo servers bound to localhost.

## Free hosted demo on Vercel

The free demo runs the Next.js frontend with `HOSTED_DEMO=true` and
`NEXT_PUBLIC_HOSTED_DEMO=true`. It serves a checked-in snapshot of the three
fictional cases, their evidence, graphs and draft PDF/JSON packets, plus the
curated source profiles. The server rejects writes with HTTP 405. It needs no
database, worker, model API or paid integration. It does not perform live scans
or persist workflow changes. Snapshot dates and grievance timers are frozen.

Create a Vercel Hobby project with root directory `frontend`, framework Next.js,
and the two flags above in Preview. Set `APP_ENV=production` and a strong
`HOSTED_OPERATOR_PASSWORD` (username `operator`). Keep the existing deployment
protection enabled. Deploy a preview using the connected account; no paid
Render resources are needed for this mode.

Regenerate only synthetic snapshot records from a fresh temporary database:

```powershell
backend\.venv\Scripts\python.exe scripts/export_hosted_demo.py
```

The exporter never reads the operator's live database. The normal local and
Render configurations continue to use the full backend when these flags are
unset. The local production smoke check is `python scripts/verify_hosted_demo.py`
against port 3100, with the password supplied via its environment.

## Full stack on Render

The root `render.yaml` defines Next.js, private FastAPI, Celery worker, a singleton Beat scheduler, PostgreSQL and Redis-compatible Render Key Value in Singapore. It uses paid service plans. Connect this GitHub repository to a Render Blueprint and supply `HOSTED_OPERATOR_PASSWORD`; the shared internal API key is generated. Optional provider keys can be added to the shared environment group later.

The API pre-deploy step migrates and seeds idempotently. Production uses PostgreSQL; startup does not silently switch to SQLite. The database's paid plan supports managed recovery; test restoration and configure operational alerting before handling real support data. Use `/ready` to monitor database and queue availability. Versions can be rolled back through Render; future schema changes require forward-compatible migrations.

## Verify

```sh
cd backend
uv run --with-requirements requirements.lock pytest -q
cd ..
npm run typecheck
npm run build
```

CI exercises PostgreSQL 16, a real Redis/Celery task, frontend builds and both Docker images. Local unit/API tests use an isolated temporary SQLite database; set `TEST_DATABASE_URL` for PostgreSQL integration testing. Generated TypeScript schemas can be refreshed with the `openapi-typescript` command against `/openapi.json`.

## Source references

- [FSSAI Food Recall Procedure Regulations, 2017](https://www.fssai.gov.in/upload/uploadfiles/files/Food_Recall_Regulations.pdf)
- [Food Safety Connect complaint workflow](https://foscos.fssai.gov.in/consumergrievance/faqs)
- [Digital Personal Data Protection Act, 2023](https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023.pdf)
- [DPDP commencement notification](https://www.meity.gov.in/static/uploads/2025/11/c56ceae6c383460ca69577428d36828b.pdf)
- Real-world product profiles carry their own original article and regulator links in the interface and `data/real_cases.json`.
