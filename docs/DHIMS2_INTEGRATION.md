# DHIMS2 integration (designed, export simulated)

**Status:** HealthConnect produces last week's totals in the **DHIS2 data format** (GHS dashboard → *Export last week for DHIMS2*). It does **not** connect to the real DHIMS2: that needs Ghana Health Service approval, accounts and official metadata, which a student project does not have.

---

## What DHIMS2 is
**DHIMS2** (District Health Information Management System 2) is the national system where Ghana's health facilities report weekly and monthly figures to the Ghana Health Service. It runs on **DHIS2**, open-source software used by health ministries in many countries.

Disease surveillance reporting follows **IDSR** (Integrated Disease Surveillance and Response): facilities report suspected cases of priority diseases (cholera, meningitis, measles, …) every week.

## Why integrate
- **No double work:** CHV visits already produce the counts; nobody re-types them into DHIMS2.
- **Faster:** weekly totals can be ready on Monday instead of waiting for paper tallies.
- **One national picture:** HealthConnect's community data joins the facility data GHS already uses.

## What we send (and what we never send)

| Sent | Never sent |
|---|---|
| **Aggregate counts**: suspected cases per condition, per district, per week | Names, references, phone numbers, notes, ages, any individual record |

Unlike the on-screen dashboard (which hides counts of 1–4 as "<5"), the DHIMS2 report uses **exact counts**: IDSR requires every suspected case of diseases like meningitis or cholera to be reported, and this is official public-health reporting to the authority responsible for it. The numbers are still totals, with no individuals.

## The format: a DHIS2 `dataValueSet`

```json
{
  "dataSet": "PLACEHOLDER_DATASET_IDSR_WEEKLY",
  "period": "2026W43",
  "completeDate": "2026-10-31",
  "dataValues": [
    { "dataElement": "PLACEHOLDER_DE_CHOLERA_SUSPECTED", "orgUnit": "PLACEHOLDER_OU_TAMALE", "value": "14" },
    { "dataElement": "PLACEHOLDER_DE_MALARIA_SUSPECTED", "orgUnit": "PLACEHOLDER_OU_BOLGATANGA", "value": "12" }
  ]
}
```

| Field | Meaning |
|---|---|
| `dataSet` | Which report form (e.g. IDSR weekly) |
| `period` | DHIS2 ISO week: `2026W43` = Monday 19 – Sunday 25 Oct 2026. We export the **last complete** week |
| `orgUnit` | The district (DHIS2 "organisation unit") |
| `dataElement` | What is counted (e.g. "cholera, suspected") |
| `value` | The count, as text (DHIS2 convention) |

The `PLACEHOLDER_…` IDs mark where the official 11-character DHIS2 **UIDs** go.

## How the real connection would work

```mermaid
sequenceDiagram
    participant S as Scheduler (EventBridge, Mondays 06:00)
    participant H as HealthConnect API
    participant D as DHIMS2 (DHIS2 Web API)
    S->>H: build last week's dataValueSet
    H->>D: GET /api/organisationUnits, /api/dataElements (once, to map our names to UIDs)
    H->>D: POST /api/dataValueSets (HTTPS, service account)
    D-->>H: import summary (imported / updated / ignored)
    H->>H: write result to audit log; alert GHS officer if anything was ignored
```

1. **Agreement:** GHS approves the integration and creates a **service account** with permission to submit data for HealthConnect's districts only (least privilege).
2. **Mapping:** download DHIMS2 metadata once (`/api/organisationUnits`, `/api/dataElements`, `/api/dataSets`) and replace each placeholder with the real UID.
3. **Schedule:** every Monday, a scheduled job (AWS EventBridge Scheduler → Lambda) builds last week's dataValueSet, the same code as our export.
4. **Send:** `POST /api/dataValueSets` over **HTTPS**, with the service account's credentials stored in **AWS Secrets Manager**, never in code.
5. **Check:** DHIS2 replies with an import summary. Store it in the audit log; if any values were rejected (e.g. an unmapped district), alert the GHS officer.
6. **Re-sending is safe:** DHIS2 overwrites a value for the same data element, org unit and period, so resending a week updates it instead of double-counting (**idempotent**).

## Built vs simulated

| Part | Status |
|---|---|
| Weekly aggregate counts by district and condition | ✅ Built (`backend/surveillance.py`) |
| DHIS2 `dataValueSet` JSON in the official shape | ✅ Built (`GET /surveillance/dhims2-export`, GHS role only, audit-logged) |
| Real DHIMS2 UIDs | ❌ Placeholders |
| Sending to DHIMS2, scheduler, import summary handling | ❌ Designed only (this document) |

## Exam points
- **Interoperability:** use the receiving system's standard format (DHIS2 dataValueSet) so data flows without re-typing.
- **Aggregate reporting:** national systems need totals, not individuals, which is data minimisation again.
- **Service accounts + least privilege:** a machine account that can *only* submit data for its own districts.
- **Idempotent uploads:** resending the same period overwrites instead of duplicating, so retries are safe.
