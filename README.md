# Kojo Tools Store

A clean content marketplace built with **Python FastAPI**.

Sell documents, Windows software (.exe) and services.  
Payments are made with **Bitcoin** (manual confirmation by admin).

**Theme:** Light/ash background · Blue buttons · Orange brand accent

---

## Features

- Login / Register
- Role-based access (Admin vs normal users)
- Admin can upload products (documents, software, services)
- Users browse products and create orders
- Bitcoin payment address shown on order page
- Admin marks orders as **Paid** → user can download digital files
- User accounts, orders and products are stored in the database

---

## Database: Use Supabase (Recommended)

Render no longer offers free PostgreSQL.  
Use your existing **Supabase** project instead — it is free and persistent.

### How to get the connection string

1. Open your Supabase project
2. Go to **Project Settings → Database**
3. Under **Connection string** choose **URI**
4. Copy the string and replace `[YOUR-PASSWORD]` with your real database password

Example:
```
postgresql://postgres.abcdefghijk:YourRealPassword@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

### Set it on Render

In your Render Web Service → Environment, add:

```
DATABASE_URL = the full connection string above
```

The app will automatically use SSL and connect to Supabase.  
All users, orders and products will survive redeployments.

---

## Quick Start (Local)

```bash
cd kojo-content-store

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your values (you can still use sqlite locally)

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000

---

## Deploy on GitHub + Render

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Kojo Tools Store"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/kojo-tools-store.git
git push -u origin main
```

### 2. Create Web Service on Render

1. Go to https://dashboard.render.com
2. **New → Web Service**
3. Connect the GitHub repository
4. Settings:
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Environment Variables:

| Key               | Value                                      |
|-------------------|--------------------------------------------|
| `DATABASE_URL`    | Your Supabase connection string            |
| `SECRET_KEY`      | Long random string                         |
| `ADMIN_EMAIL`     | your admin email                           |
| `ADMIN_PASSWORD`  | Strong password                            |
| `BITCOIN_ADDRESS` | Your real Bitcoin address                  |
| `SITE_NAME`       | Kojo Tools Store                           |

6. Create Web Service

---

## How Bitcoin Payment Works

1. User clicks **Buy Now**
2. Order is created (`pending`)
3. User sees your Bitcoin address + exact amount
4. User sends BTC (can paste TX ID)
5. You go to **Admin panel** → click **Mark Paid**
6. User can download the file

---

Made by Kojo
