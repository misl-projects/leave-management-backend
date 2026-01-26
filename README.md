# MISL Leave Management Workflow

## 📝 Description
This repository contains the **automated leave management workflow** for MISL. It handles incoming employee leave requests sent via email, applies company leave rules, notifies relevant parties, and logs all leave activity in the database. 

This workflow is the backend engine powering the leave approval process and supports the MISL admin dashboard.

---

## ⚙️ Workflow Overview

1.  **Employee Request:** Employees send leave requests via company email specifying dates and reasons.
2.  **Capture & Processing:** A **FastAPI service** polls for new emails every 15 seconds to:
    * Validate the sender is a MISL employee.
    * Detect leave intent and extract metadata (start/end dates, reason).
    * Fetch employee records (balance, role, salary) from **Supabase**.
3.  **Business Logic (Python + LLM):** Requests are auto-evaluated based on:
    * Remaining leave balance and 3-day notice periods.
    * Date validity.
    * **LLM Integration:** Used for free-text identification, metadata extraction, and drafting human-readable emails (rejections or finance notices).
4.  **Automated Responses:**
    * **Employees:** Receive approval/rejection status and remaining balance.
    * **Finance:** Receive salary deduction details if applicable via Gmail API.
5.  **Data Persistence:** All history and master records are stored in **Supabase** as the single source of truth.

---

## 📂 Repository Structure

```text
.
├── app.py                      # FastAPI app to run the workflow scheduler
├── leave_management_workflow.py # Main workflow logic (processing & decision making)
├── llm/                         # AI modules for detection and email drafting
├── tools/                       # Utilities (Supabase helpers, OAuth credentials)
├── requirements.txt            # Python dependencies
├── vercel.json                 # Vercel deployment configuration
├── .gitignore                  # Ignored files (tokens, env files, etc.)
└── README.md                   # Project documentation

```

# Key Files

- **`app.py`**  
  Runs the FastAPI server and schedules the workflow to process incoming emails periodically.

- **`leave_management_workflow.py`**  
  Core workflow logic: processes emails, validates requests, applies business rules, triggers email notifications, and updates the database.

- **`llm/`**  
  Contains modules for:
  - Detecting leave requests in email text
  - Extracting leave metadata (start date, end date, reason)
  - Drafting automated emails to employees and finance
  - Calculating salary deductions if required

- **`tools/`**  
  Helper utilities for:
  - Interacting with Supabase database  
  - Managing OAuth credentials for Gmail API  

- **`requirements.txt`**  
  Python packages required to run the workflow, including FastAPI, APScheduler, Google API client, and Supabase SDK.

---

## Getting Started

1. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

2. Add your Google OAuth credentials in a secure api/token.json file.

3. Update allowed domains in leave_management_workflow.py if needed:

    ```bash
    ALLOWED_DOMAINS = ["mislsolutions.com", "hassanrevel.com"]
    ```

4. Run the FastAPI workflow service:

    ```bash
    python app.py
    ```


## Notes

- Only approved company domains can submit leave requests.

- Emails are automatically labeled in Gmail once processed.

- All leave actions are logged in Supabase to maintain a single source of truth.

- The workflow is fully automated, but admin approval functionality is supported through the dashboard.