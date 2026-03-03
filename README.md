# MISL Leave Management Workflow (Backend Automation)

Python workflow service for automated leave processing in MISL.  
It reads leave request emails, evaluates policy rules, updates Supabase, and sends notification emails to employees and finance.

## What This Service Does

- Polls Gmail inbox every 15 seconds.
- Filters senders by allowed domain + verifies employee in Supabase.
- Detects if an email is actually a leave request.
- Extracts structured leave metadata from free-text emails.
- Applies leave decision logic (`approved`, `pending`, `rejected`).
- Stores leave records in Supabase (`employee_leaves`).
- Sends decision email to employee.
- Sends finance deduction email when leave is rejected.
- Processes admin override events from DB queue and notifies users.
- Labels processed Gmail messages to avoid duplicate processing.

## Business Rules Implemented

The decision model enforces these core rules:

- If employee has no remaining leaves: `rejected`.
- If leave dates are missing/unclear: `pending`.
- If prior notice is 3+ calendar days and request is valid: `approved`.
- If prior notice is under 3 days:
  - Emergency-like reasons: `pending`.
  - Non-emergency reasons: `rejected`.
- If leave days exceed remaining balance: `rejected`.
- Invalid or unclear cases default to `pending`.

Salary deduction is calculated only for `rejected` leaves:

- `daily_salary = basic_salary / 30`
- `deduction = daily_salary * leave_days`

## Stack

- FastAPI
- APScheduler
- Gmail API (read/send/label)
- Supabase Python SDK
- LangChain + Groq/Gemini model clients

## Repository Structure

```text
.
├── app.py                         # FastAPI app + schedulers
├── leave_management_workflow.py   # Main email processing + override notifications
├── llm/
│   ├── llm.py                     # LLM client setup
│   ├── is_leave_request.py
│   ├── extract_leave_metadata.py
│   ├── decide_leave_application.py
│   ├── calculate_salary_deduction.py
│   └── draft_email.py
├── tools/
│   ├── oauth_utils.py             # Gmail OAuth token management
│   └── supabase_utils.py          # DB queries/helpers
├── requirements.txt
└── vercel.json
```

## Required Data Model (Supabase)

This service expects these tables:

- `employees`
- `employee_leaves`
- `leave_status_change_events` (notification queue for manual status overrides)

Expected behavior:

- Dashboard updates `employee_leaves.status`.
- A DB trigger/process should insert a queue row into `leave_status_change_events`.
- This workflow picks queue rows with `notification_status = pending` and sends notifications.

## Environment Variables

Create `.env` in `misl_workflow`:

```bash
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_KEY=YOUR_SUPABASE_SERVICE_OR_SECRET_KEY
FINANCE_EMAIL=finance@yourcompany.com

# One LLM provider is required by llm/llm.py
GROQ_API_KEY=YOUR_GROQ_KEY
# Optional if you switch to Gemini model:
GOOGLE_API_KEY=YOUR_GOOGLE_GENAI_KEY
```

## OAuth Files Required (Gmail)

Place these files in the `misl_workflow` root:

- `credentials.json` (Google OAuth client credentials)
- `token.json` (generated after first auth)

On first run, OAuth flow opens locally and generates `token.json`.

## Installation & Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Ensure env vars + OAuth files are present.
3. Start the API and scheduler:

```bash
python app.py
```

Default endpoint:

- `GET /` -> health/status response

## Scheduled Jobs

Defined in `app.py`:

- `process_incoming_emails` every 15 seconds
- `process_status_change_notifications` every 15 seconds

## Deployment

- `vercel.json` is configured to deploy `app.py` as a Python serverless function.
- If long-running scheduled background work is required, prefer a persistent runtime (VM/container) instead of pure serverless execution.

## Notes

- Allowed sender domains are hardcoded in `leave_management_workflow.py` (`ALLOWED_DOMAINS`) and should match company policy.
- Processed messages are labeled using Gmail label `MISL_LEAVE_PROCESSED`.
- Duplicate/overlapping leave ranges for the same employee are blocked before insert.
- Existing `requirements.txt` may need `python-dotenv` if not already installed in your runtime.
