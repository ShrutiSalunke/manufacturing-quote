# Manufacturing Quote MVP

Configurable manufacturing quote costing system built with **Django 5.x**, Bootstrap 5, and an in-process formula engine. Excel is used only for master-data import/export — **not** as the calculation engine. Customer output is **PDF only**. Application errors are stored in the **SystemLog database table** and browsed in the **Error Logs** UI (not written to a separate log file).

## Requirements

- Python 3.11+ (Django 5.2 supports current Python releases including 3.14)
- SQLite by default (PostgreSQL optional via `DATABASE_URL`)
- Django 5.2.x (see `requirements.txt`)

## Quick start

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # or: cp .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open http://127.0.0.1:8000/

### Default users

| Role   | Username / login        | Password   |
|--------|-------------------------|------------|
| Admin  | `admin@example.com`     | `Admin123!` |
| Quoter | `quoter@example.com`    | `Quoter123!` |

Admin can configure masters, custom fields, templates, and Error Logs. Quoter can create quotes and generate PDFs.

### Defaults documented here

- Local DB: SQLite file `db.sqlite3`
- Currency / plant: `MAIN` plant, INR, timezone `Asia/Kolkata`
- Company name on PDF: `COMPANY_NAME` env (default `Prasad Manufacturing`)
- Tour: enabled via `AppSetting` key `tour_enabled=true`
- PDF engine: `xhtml2pdf` (pure Python; WeasyPrint optional alternative not required)

## Demo path (&lt; 10 minutes)

1. Sign in as Admin.
2. Follow the product tour (or click **Restart product tour**).
3. Open **Imports** → download Materials template (or use `excel_templates/samples/materials_sample.xlsx`).
4. Upload the sample → confirm rows in **Catalog → Materials**.
5. Open **Product Templates → Sheet Metal Box** → run **Test calculator** (expect non-zero material & machine cost).
6. Open **Quotes → Q-DEMO-001** → **Calculate** → view internal cost breakdown.
7. Click **Generate / Download PDF** (customer PDF shows selling prices only).

## How to add a custom Excel column (no code)

1. Admin → **Custom Fields** → **Add field**.
2. Choose entity (e.g. Material), set `key`, label, data type, check **Importable**.
3. Download the Materials template again — the new column header appears automatically.
4. Fill values in Excel and import; values are stored as `CustomFieldValue`.

## How to add a new product type (no code)

1. Admin → **Product Templates → New template** (pick family/plant).
2. Add parameters, formulas, BOM items, operations, cost elements, margin.
3. Use **Test calculator**, then **Publish**.
4. On a quote, **Add line** and select the published template.
5. To change a published template without breaking old quotes: **Save as new version**.

## How to view errors

- Open **Error Logs** in the app (Admin only).
- Every ERROR/CRITICAL (imports, costing, PDF, unhandled exceptions) is stored in the **`SystemLog` database table**.
- **Errors are not written to a separate log file** (`logs/app.log` is not used). Console output during `runserver` is optional debug only.
- When an operation fails, the flash message includes a **correlation id**. Paste that id into the Error Logs search box to open the matching row (full traceback + context JSON).
- Response header `X-Correlation-Id` is also set on every request.

## PostgreSQL (optional)

Set in `.env`:

```
DATABASE_URL=postgres://user:password@localhost:5432/manufacturing_quote
```

Then `migrate` as usual.

## Deploy on Render

This project includes `render.yaml`, `Procfile`, Gunicorn, and WhiteNoise.

1. Push this repo to GitHub (see commands below — run them yourself so the commits are yours).
2. In [Render](https://dashboard.render.com): **New → Blueprint** → select the repo → apply.
3. Or create manually:
   - **PostgreSQL** database
   - **Web Service** (Python):
     - Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate --noinput`
     - Start: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
4. Environment variables:
   - `DJANGO_SECRET_KEY` — random secret (Blueprint can generate)
   - `DJANGO_DEBUG` — `False`
   - `DATABASE_URL` — from the Render Postgres instance
   - `DATABASE_SSL` — `true`
   - `DJANGO_ALLOWED_HOSTS` — your host, e.g. `manufacturing-quote.onrender.com` (optional if `RENDER_EXTERNAL_HOSTNAME` is set)
   - `CSRF_TRUSTED_ORIGINS` — e.g. `https://manufacturing-quote.onrender.com` (optional if `RENDER_EXTERNAL_HOSTNAME` is set)
5. After the first successful deploy, open **Shell** on the web service and seed demo data:

```bash
python manage.py seed_demo
```

**Notes:** Free web services sleep when idle. Uploaded Excel/PDF files on the free disk are ephemeral (redeploys can clear `media/`). Errors still go to the **Error Logs** UI (database), not a log file.

## Tests

```bash
python manage.py test apps.core.tests -v 2
python manage.py check
```

## Project layout

```
apps/
  accounts/          # users + ADMIN|QUOTER roles
  core/              # plants, logging helpers, dashboard, seed
  catalog/           # materials, machines, labor, custom fields
  templates_engine/  # product templates / BOM / ops / formulas
  costing/           # safe formula engine + cost rollup
  quotes/            # quotes, snapshots, PDF
  imports_excel/     # template download + import jobs
  onboarding/        # Shepherd.js tour state
  auditlog/          # SystemLog model + Error Logs UI + DB handler
excel_templates/     # blank + sample xlsx
```

## Costing conventions

- Setup time formulas: minutes **per batch/line** (not multiplied by `LINE_QTY`)
- Cycle / labor time formulas: minutes **per piece** (multiplied by `LINE_QTY`)
- Named formulas evaluate in dependency order (cycles are rejected)
- Cost elements evaluate after material/machine/labor and may use `TOTAL_MATERIAL`, `TOTAL_MACHINE`, `TOTAL_LABOR`
- Margin: `MARGIN_PERCENT` is margin on sell → `selling = total_cost / (1 - margin/100)`
