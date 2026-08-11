from sqlalchemy import text
from fastapi import FastAPI, Request, Depends, Form, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
import os
import shutil
import uuid
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

from .database import engine, Base, get_db
from .models import User, Product, Order
from .auth import (
    get_password_hash, authenticate_user, create_access_token,
    get_current_user, require_user, require_admin
)

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Kojo Tools Store")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
UPLOAD_DIR = Path("app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SITE_NAME = os.getenv("SITE_NAME", "Kojo Tools Store")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "") # Your gmail
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "") # Your gmail app password

def send_email(to_email: str, subject: str, body: str):
    if not SMTP_EMAIL: return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SITE_NAME
        msg["To"] = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
    except Exception as e:
        print(f"Email error: {e}")

def create_admin_if_needed(db: Session):
    try:
        admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not admin:
            admin = User(email=ADMIN_EMAIL, hashed_password=get_password_hash(ADMIN_PASSWORD), full_name="Admin", is_admin=True)
            db.add(admin)
            db.commit()
            print(f"✅ Admin created: {ADMIN_EMAIL}")
    except Exception as e:
        print(f"⚠️ Could not create/check admin: {e}")
        db.rollback()

@app.on_event("startup")
def startup():
    db = next(get_db())
    try:
        db.execute(text("ALTER TABLE products RENAME COLUMN price_btc TO price_usd"))
        db.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url VARCHAR"))
        db.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS price_usd_approx"))
        db.execute(text("ALTER TABLE orders RENAME COLUMN amount_btc TO amount_usd"))
        db.execute(text("ALTER TABLE orders RENAME COLUMN tx_id TO notes"))
        db.commit()
        print("✅ DB Migrated to USD + Image")
    except Exception as e:
        db.rollback()
        print(f"ℹ️ DB already migrated or new: {e}")
    
    create_admin_if_needed(db)
    db.close()

def render(request: Request, name: str, context: dict = None, user=None):
    ctx = {"request": request, "site_name": SITE_NAME, "user": user}
    if context: ctx.update(context)
    return templates.TemplateResponse(name, ctx)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user=Depends(get_current_user)):
    if user: return RedirectResponse("/dashboard", status_code=303)
    return render(request, "index.html")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user=Depends(get_current_user)):
    if user: return RedirectResponse("/dashboard", status_code=303)
    return render(request, "login.html")

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate_user(db, email, password)
    if not user: return render(request, "login.html", {"error": "Invalid email or password"})
    token = create_access_token({"sub": user.email})
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=60 * 60 * 24 * 7)
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user=Depends(get_current_user)):
    if user: return RedirectResponse("/dashboard", status_code=303)
    return render(request, "register.html")

@app.post("/register")
async def register(request: Request, full_name: str = Form(""), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == email).first(): return render(request, "register.html", {"error": "Email already registered"})
    if len(password) < 6: return render(request, "register.html", {"error": "Password must be at least 6 characters"})
    user = User(email=email, hashed_password=get_password_hash(password), full_name=full_name)
    db.add(user)
    db.commit()
    token = create_access_token({"sub": user.email})
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=60 * 60 * 24 * 7)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(require_user), db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.is_active == True).order_by(Product.created_at.desc()).all()
    orders = db.query(Order).filter(Order.user_id == user.id).order_by(Order.created_at.desc()).all()
    return render(request, "dashboard.html", {"products": products, "orders": orders}, user=user)

@app.post("/buy/{product_id}")
async def buy_product(product_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product: raise HTTPException(status_code=404, detail="Product not found")
    order = Order(user_id=user.id, product_id=product.id, amount_usd=product.price_usd, status="pending")
    db.add(order)
    db.commit()
    db.refresh(order)
    return RedirectResponse(f"/order/{order.id}", status_code=303)

@app.get("/order/{order_id}", response_class=HTMLResponse)
async def order_page(order_id: int, request: Request, user=Depends(require_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order: raise HTTPException(status_code=404, detail="Order not found")
    return render(request, "order.html", {"order": order}, user=user)

@app.post("/order/{order_id}/confirm")
async def confirm_payment(order_id: int, notes: str = Form(""), user=Depends(require_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order: raise HTTPException(status_code=404, detail="Order not found")
    order.notes = notes.strip()
    db.commit()
    return RedirectResponse(f"/order/{order_id}", status_code=303)

@app.get("/download/{order_id}")
async def download_file(order_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order or order.status != "paid": raise HTTPException(status_code=403, detail="Payment not confirmed")
    if not order.product.file_path: raise HTTPException(status_code=404, detail="No file available")
    file_path = UPLOAD_DIR / order.product.file_path
    if not file_path.exists(): raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=file_path.name)

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, user=Depends(require_admin), db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.created_at.desc()).all()
    orders = db.query(Order).order_by(Order.created_at.desc()).limit(50).all()
    return render(request, "admin.html", {"products": products, "orders": orders}, user=user)

@app.post("/admin/upload")
async def admin_upload(title: str = Form(...), category: str = Form("document"), description: str = Form(""), price_usd: float = Form(...), image_url: str = Form(""), file: UploadFile = File(None), user=Depends(require_admin), db: Session = Depends(get_db)):
    file_path = None
    if file and file.filename:
        ext = Path(file.filename).suffix
        unique_name = f"{uuid.uuid4().hex}{ext}"
        dest = UPLOAD_DIR / unique_name
        with open(dest, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        file_path = unique_name
    product = Product(title=title, description=description, category=category, price_usd=price_usd, image_url=image_url, file_path=file_path, is_active=True)
    db.add(product)
    db.commit()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/toggle/{product_id}")
async def toggle_product(product_id: int, user=Depends(require_admin), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product: product.is_active = not product.is_active; db.commit()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/order/{order_id}/mark-paid")
async def mark_paid(order_id: int, background_tasks: BackgroundTasks, user=Depends(require_admin), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order: 
        order.status = "paid"
        db.commit()
        # OPTION C: Auto-email customer with Spam note
        if order.product.file_path:
            body = f"""Thanks! Your payment for '{order.product.title}' is confirmed.

Download here: https://your-site.com/download/{order.id}

Can't find the email? Please check your Spam/Junk/Promotions folder.
"""
        else:
            body = f"""Thanks, we received your payment. 

We will deliver your '{order.product.title}' to this email within 24hrs.

Can't find our emails? Please check your Spam/Junk/Promotions folder and add us to your contacts.
"""
        background_tasks.add_task(send_email, order.user.email, f"Order #{order.id} Confirmed - {SITE_NAME}", body)
    return RedirectResponse("/admin", status_code=303)

@app.get("/health")
def health(): return {"status": "healthy", "site": SITE_NAME}
