# Meridian Systems — PyQt5 Client

Desktop UI for the Employee Management System backend, built to match
the architecture in the project README (**PyQt5 = View, FastAPI =
Controller, MySQL = Model**) and the flows in `DFD_Documentation_v2.docx`.

## Structure

```
client/
├── main.py                    Entry point — run this
├── requirements.txt
├── controllers/                Talks to the FastAPI backend over HTTP.
│   ├── api_client.py            Low-level requests wrapper, holds the JWT,
│   │                            turns HTTP errors into APIError.
│   ├── auth_controller.py       login / set-password / forgot-reset / me
│   ├── employee_controller.py   create/suspend/reactivate/update/history
│   ├── org_controller.py        departments / positions / shifts
│   ├── leave_controller.py      apply / decide / balance
│   ├── attendance_controller.py check-in / check-out / history
│   ├── overtime_controller.py   apply / decide / history
│   ├── holiday_controller.py    list / create
│   ├── notification_controller.py list / mark-read
│   └── audit_controller.py      view audit trail
├── views/                       PyQt5 windows/widgets (the "View").
│   ├── login_view.py             sign-in, lockout messages
│   ├── change_password_dialog.py first-login reset + voluntary change
│   ├── forgot_password_dialog.py OTP-based reset for logged-out users
│   ├── main_window.py            role-based tab shell
│   ├── dashboard_view.py, profile_view.py
│   ├── employees_view.py (+ employee_form_dialog, employee_history_dialog)
│   ├── org_view.py               departments/positions/shifts (Admin only)
│   ├── leave_view.py, attendance_view.py, overtime_view.py
│   ├── holidays_view.py, notifications_view.py, audit_view.py
│   └── common.py                 shared table/dialog helpers
└── resources/styles/style.qss   Application stylesheet
```

## Running it

1. Set up and start the backend first (see the top-level `README.md`):
   ```bash
   cd database && python create_db.py
   cd ../backend && python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   python seed_admin.py
   uvicorn app.main:app --reload --port 8000
   ```
2. In a second terminal, set up and run the client:
   ```bash
   cd client
   python -m venv venv && source venv/bin/activate   # optional but recommended
   pip install -r requirements.txt
   python main.py
   ```
3. Log in with the seeded admin (`priya.nair@meridian.com` / `Admin@123`,
   or whatever you changed it to in `backend/seed_admin.py`). From there,
   the Admin creates every other user through the **Employees** tab —
   exactly like the original module-flow diagram describes.

The login screen has a **Server** field pre-filled with
`http://127.0.0.1:8000` in case you run the backend on a different host
or port.

## Role-based tabs

The main window only shows the tabs each role can actually use, per the
Roles & Permissions matrix in `API_REFERENCE.md`:

| Tab | Admin | HR | Manager | Employee |
|---|:---:|:---:|:---:|:---:|
| Dashboard | ✅ | ✅ | ✅ | ✅ |
| Employees | ✅ | ✅ (edit/suspend/reactivate only — see below) | ❌ | ❌ |
| Organization (departments/positions/shifts) | ✅ | ❌ | ❌ | ❌ |
| Leave | ✅ | ✅ | ✅ | ✅ |
| Attendance | ✅ | ✅ | ✅ | ✅ |
| Overtime | ✅ | ✅ | ✅ | ✅ |
| Holidays | ✅ | ✅ | ✅ | ✅ |
| Notifications | ✅ | ✅ | ✅ | ✅ |
| Audit Log | ✅ | ✅ | ❌ | ❌ |
| My Account | ✅ | ✅ | ✅ | ✅ |

Self-service actions (check-in/out, apply leave/overtime) only work if
the logged-in account is linked to an employee record with a shift
assigned — a pure system account gets a clear error message instead of
a crash, matching the backend's own `"This account is not linked to an
employee record."` response.

## Two backend gaps this client works around

While wiring this client up against the real API, two gaps in the
current backend surface (documented here so they're easy to close
later — they don't block using the app today):

1. **No `GET /api/employment-types` endpoint.** `EmployeeCreateRequest`
   requires an `employment_type_id`, but there's no way to fetch the
   list from the API. `controllers/org_controller.py` ships a fallback
   list (`EMPLOYMENT_TYPES_FALLBACK`) matching the exact seed data in
   `database/schema.sql` (Full-time / Part-time / Contract / Intern /
   Probation, IDs 1–5). If you add a real endpoint later, swap that
   fallback for an `api_client.get(...)` call — one line to change.

2. **No endpoint to list leave requests** (own or all) — only
   `POST /api/leave-requests`, `PUT .../decision`, and
   `GET .../me/balance` exist. The **Leave → Pending approvals** panel
   is therefore built on top of your own notifications design: applying
   for leave already notifies the manager with
   `reference_table="leave_requests"` and `reference_id=<leave_request_id>`,
   so the panel reads the approver's notifications and lets them decide
   straight from there. A manual "decide by leave request ID" fallback
   is included too, in case a notification was already deleted/missed.
   Adding a real `GET /api/leave-requests` (own) and
   `GET /api/leave-requests?status=Pending` (all, scoped by
   `manage_leave`/manager team) endpoint would let this panel work like
   the Overtime tab's, which already has proper list endpoints.

## Creating HR and Manager accounts

There's no public registration page — every account is provisioned by
an **Admin**, and only an Admin, from inside the **Employees** tab:

- **New Employee dialog** — only visible to Admin at all (HR does not
  see a "+ New Employee" button). Has a **Role** dropdown covering all
  four roles (`Employee` / `Manager` / `HR` / `Admin`).
- **Change Role button** — also Admin-only. Select any employee in the
  table and click **Change Role** to promote/demote them later. Nobody
  can change their own role, including Admin, to avoid accidental
  self-lockout.
- **HR's Employees tab** shows the same table (list/view) and keeps
  Edit / Suspend / Reactivate, but has no "New Employee" or "Change
  Role" button — creating an account or changing its role requires the
  `assign_roles` permission, which only Admin has (see
  `database/schema.sql`). Calling the API directly with an HR token
  returns `403 "Your role does not have the 'assign_roles' permission."`

So in practice: log in as the seeded Admin, create every account
directly — including the first HR/Manager accounts — with the Role
dropdown. HR then handles day-to-day employee management (edit,
suspend, reactivate, approve leave/overtime) but never creates
accounts or touches anyone's role.

## Notes on error handling

Every controller call can raise `controllers.api_client.APIError`
(network failure, or the backend's own 4xx/5xx with its `detail`
message). Every view catches this and shows it as a `QMessageBox`
rather than crashing — including the account-lockout (423) and
suspended-account (403) messages from `auth_controller.py` on the
backend, which are shown to the user verbatim.
