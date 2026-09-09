# Data Flow

## What moves where

```
  CV file on the user's laptop
        │  read locally
        ▼
  extracted text  ──────────────► Groq API (HTTPS)
        │                          returns JSON judgments
        │                          nothing is retained for training
        ▼
  quote verification (local, no network)
        ▼
  SQLite  data/sift.db  ──────►  CSV / Google Sheet   (explicit user action)
        │
        └───────────────────────►  Gmail SMTP          (explicit user action,
                                                        GREAT FIT only)
```

## What leaves the machine

| Data | Destination | Trigger |
|---|---|---|
| Extracted CV text | Groq API, over TLS | Every screening |
| Candidate name, tier, evidence | Spreadsheet or CSV | User clicks Export |
| Candidate name + email + invitation | Gmail SMTP | User clicks Send, per candidate |

**Nothing else leaves.** The original file never does. No analytics, no
telemetry, no third-party services.

## What is stored, and where

| Path | Contents | In version control |
|---|---|---|
| `data/sift.db` | Every run, judgment, exception and human override | no |
| `data/real_cvs/` | Real CVs supplied by the user | no |
| `data/sent_emails.log` | Every invitation, dry-run and real | no |
| `.env` | API key, SMTP credentials | no (mode 600) |
| `credentials/` | Service-account keys | no |
| `eval/cases/` | Anonymised test CVs | yes |
| `samples/` | Synthetic example CVs | yes |

## Personal data

CVs are personal data about people who did not consent to this project.

- Processing is local; only extracted text crosses the network.
- Real CVs are excluded from version control by `.gitignore`.
- The committed test set is anonymised by `eval/anonymise.py`, which replaces
  names, emails, phone numbers and URLs — and then **verifies its own output
  against the original**, failing if any identifier survives. That verification
  exists because the first three versions of the script leaked.
- Deleting `data/` removes everything the system holds.

## Permission boundaries

- Read-only access to CV files. No writes, moves or deletes.
- No calendar access, no booking.
- No writes to any applicant tracking system.
- Outbound mail is send-only, one message at a time, never in bulk, gated on
  fit tier plus two explicit human clicks, and off by default.
