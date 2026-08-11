from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
from .database import engine, get_db, Base
from . import models, schemas, crud, auth
from .config import settings

app = FastAPI(title=settings.SITE_NAME)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def render(request: Request, name: str, context: dict = None, user=None):
    ctx = {"request": request, "site_name": settings.SITE_NAME, "user": user}
    if context: ctx.update(context)
    return templates.TemplateResponse(name, ctx)

def safe_execute(db: Session, sql: str):
    try:
        db.execute(text(sql))
        db.commit()
    except Exception as e:
        print(f"Migration note: {e}")
        db.rollback()

@app.on_event("startup")
def startup():
    db = next(get_db())
    print("🔄 Running DB Migrations...")
    
    safe_execute(db, "ALTER TABLE products RENAME COLUMN IF EXISTS price_btc TO price_usd")
    safe_execute(db, "ALTER TABLE products ADD COLUMN IF NOT EXISTS price_usd FLOAT DEFAULT 0")
    safe_execute(db, "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url VARCHAR")
    
    safe_execute(db, "ALTER TABLE orders RENAME COLUMN IF EXISTS amount_btc TO amount_usd")
    safe_execute(db, "ALTER TABLE orders ADD COLUMN IF NOT EXISTS amount_usd FLOAT DEFAULT 0")
    safe_execute(db, "ALTER TABLE orders RENAME COLUMN IF EXISTS tx_id TO notes")
    safe_execute(db, "ALTER TABLE orders ADD COLUMN IF NOT EXISTS notes VARCHAR")
    
    print("✅ DB Migration Check Done")
    crud.create_admin_if_needed(db)
    db.close()

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, db: Session = Depends(get_db)):
    products = crud.get_products(db)
    return render(request, "index.html", {"products": products})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), user=Depends(auth.get_current_user)):
    products = crud.get_products(db)
    orders = crud.get_orders(db, user.id)
    return render(request, "dashboard.html", {"products": products, "orders": orders}, user)

@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return render(request, "register.html")

@app.post("/register")
def register_post(username: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email)
    if user: raise HTTPException(status_code=400, detail="Email already registered")
    crud.create_user(db, schemas.UserCreate(username=username, email=email, password=password))
    return RedirectResponse(url="/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return render(request, "login.html")

@app.post("/login")
def login_post(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = auth.authenticate_user(db, email, password)
    if not user: raise HTTPException(status_code=400, detail="Incorrect email or password")
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=user.email, httponly=True)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response
