from fastapi import FastAPI, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
import os
import shutil
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from supabase import create_client, Client

from .database import engine, Base, get_db
from .models import User, Product, Order
from .auth import (
    get_password_hash, authenticate_user, create_access_token,
    get_current_user, require_user, require_admin
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Kojo Tools Store")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")

templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = Path("app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "images").mkdir(parents=True, exist_ok=True)

# Environment
SITE_NAME = os.getenv("SITE_NAME", "Kojo Tools Store")
BITCOIN_ADDRESS = os.getenv("BITCOIN_ADDRESS", "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SITE_URL = "https://kojo-content-store.onrender.com"

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client ready")
    except Exception as e:
        print(f"⚠️ Supabase init failed: {e}")


def upload_image_to_supabase(file: UploadFile) -> str | None:
    if not supabase or not file or not file.filename:
        return None
    try:
        ext = Path(file.filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
            return None
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_bytes = file.file.read()
        supabase.storage.from_("product-images").upload(
            path=unique_name,
            file=file_bytes,
            file_options={"content-type": file.content_type or "image/jpeg"}
        )
        return supabase.storage.from_("product-images").get_public_url(unique_name)
    except Exception as e:
        print(f"❌ Supabase upload failed: {e}")
        return None


def send_email(to_email: str, subject: str, body: str):
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False


def create_admin_if_needed(db: Session):
    try:
        admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not admin:
            admin = User(
                email=ADMIN_EMAIL,
                hashed_password=get_password_hash(ADMIN_PASSWORD),
                full_name="Admin",
                is_admin=True,
                credits=0.0
            )
            db.add(admin)
            db.commit()
            print(f"✅ Admin created: {ADMIN_EMAIL}")
    except Exception as e:
        print(f"⚠️ Admin check failed: {e}")
        db.rollback()


@app.on_event("startup")
def startup():
    try:
        db = next(get_db())
        create_admin_if_needed(db)
        db.close()
    except Exception as e:
        print(f"⚠️ Startup warning: {e}")


def render(request: Request, name: str, context: dict = None, user=None):
    ctx = {"request": request, "site_name": SITE_NAME, "user": user}
    if context:
        ctx.update(context)
    return templates.TemplateResponse(name, ctx)


# ==================== AUTH ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "index.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "login.html")


@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate_user(db, email, password)
    if not user:
        return render(request, "login.html", {"error": "Invalid email or password"})
    token = create_access_token({"sub": user.email})
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=60*60*24*7)
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "register.html")


@app.post("/register")
async def register(request: Request, full_name: str = Form(""), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == email).first():
        return render(request, "register.html", {"error": "Email already registered"})
    if len(password) < 6:
        return render(request, "register.html", {"error": "Password must be at least 6 characters"})
    user = User(email=email, hashed_password=get_password_hash(password), full_name=full_name, credits=0.0)
    db.add(user)
    db.commit()
    token = create_access_token({"sub": user.email})
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=60*60*24*7)
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response


# ==================== DASHBOARD ====================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(require_user), db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.is_active == True).order_by(Product.created_at.desc()).all()
    orders = db.query(Order).filter(Order.user_id == user.id).order_by(Order.created_at.desc()).all()
    return render(request, "dashboard.html", {
        "products": products,
        "orders": orders,
        "credits": user.credits or 0.0
    }, user=user)


# ==================== BUY / ORDER ====================

@app.post("/buy/{product_id}")
async def buy_product(product_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Pay with Store Credit
    if (user.credits or 0) >= product.price_usd:
        user.credits = (user.credits or 0) - product.price_usd
        order = Order(
            user_id=user.id,
            product_id=product.id,
            amount_usd=product.price_usd,
            status="paid",
            payment_type="credits",
            notes="Paid with Store Credit"
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return RedirectResponse(f"/order/{order.id}?success=credits", status_code=303)

    # Create pending BTC order
    order = Order(
        user_id=user.id,
        product_id=product.id,
        amount_usd=product.price_usd,
        status="pending",
        payment_type="btc"
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return RedirectResponse(f"/order/{order.id}", status_code=303)


@app.get("/order/{order_id}", response_class=HTMLResponse)
async def order_page(order_id: int, request: Request, user=Depends(require_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    success = request.query_params.get("success")
    return render(request, "order.html", {
        "order": order,
        "bitcoin_address": BITCOIN_ADDRESS,
        "success": success
    }, user=user)


@app.post("/order/{order_id}/confirm")
async def confirm_payment(order_id: int, notes: str = Form(""), user=Depends(require_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "pending":
        order.notes = notes.strip() or order.notes or "User clicked I have paid"
        db.commit()
    return RedirectResponse(f"/order/{order_id}?submitted=1", status_code=303)


@app.get("/download/{order_id}")
async def download_file(order_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order or order.status != "paid":
        raise HTTPException(status_code=403, detail="Payment not confirmed")
    if not order.product.file_path:
        raise HTTPException(status_code=404, detail="No file available for this product")
    file_path = UPLOAD_DIR / order.product.file_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on server")
    return FileResponse(path=file_path, filename=file_path.name)


# ==================== ADMIN ====================

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, user=Depends(require_admin), db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.created_at.desc()).all()
    orders = db.query(Order).order_by(Order.created_at.desc()).limit(50).all()
    pending_orders = [o for o in orders if o.status == "pending"]
    return render(request, "admin.html", {
        "products": products,
        "orders": orders,
        "pending_orders": pending_orders
    }, user=user)


@app.post("/admin/upload")
async def admin_upload(
    title: str = Form(...),
    category: str = Form("document"),
    description: str = Form(""),
    price_usd: float = Form(...),
    image_url: str = Form(""),
    image: UploadFile = File(None),
    file: UploadFile = File(None),
    user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Digital file
    file_path = None
    if file and file.filename:
        ext = Path(file.filename).suffix
        unique_name = f"{uuid.uuid4().hex}{ext}"
        dest = UPLOAD_DIR / unique_name
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_path = unique_name

    # Image → Supabase
    final_image_url = image_url.strip() or None
    if image and image.filename:
        uploaded = upload_image_to_supabase(image)
        if uploaded:
            final_image_url = uploaded

    product = Product(
        title=title,
        description=description,
        category=category,
        price_usd=price_usd,
        image_url=final_image_url,
        file_path=file_path,
        is_active=True
    )
    db.add(product)
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin/product/{product_id}/edit", response_class=HTMLResponse)
async def edit_product_page(product_id: int, request: Request, user=Depends(require_admin), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return render(request, "edit_product.html", {"product": product}, user=user)


@app.post("/admin/product/{product_id}/edit")
async def edit_product(
    product_id: int,
    title: str = Form(...),
    category: str = Form("document"),
    description: str = Form(""),
    price_usd: float = Form(...),
    image_url: str = Form(""),
    image: UploadFile = File(None),
    file: UploadFile = File(None),
    is_active: str = Form("true"),
    user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.title = title
    product.category = category
    product.description = description
    product.price_usd = price_usd
    product.is_active = is_active == "true"

    # New image
    if image and image.filename:
        uploaded = upload_image_to_supabase(image)
        if uploaded:
            product.image_url = uploaded
    elif image_url.strip():
        product.image_url = image_url.strip()

    # New or replacement digital file
    if file and file.filename:
        ext = Path(file.filename).suffix
        unique_name = f"{uuid.uuid4().hex}{ext}"
        dest = UPLOAD_DIR / unique_name
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        product.file_path = unique_name

    db.commit()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/toggle/{product_id}")
async def toggle_product(product_id: int, user=Depends(require_admin), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.is_active = not product.is_active
        db.commit()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/order/{order_id}/mark-paid")
async def mark_paid(order_id: int, user=Depends(require_admin), db: Session = Depends(get_db)):
    """Mark as Paid → appears in customer Order History + Download button + email"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if order and order.status == "pending":
        order.status = "paid"
        db.commit()

        try:
            subject = f"Your order #{order.id} is confirmed – {SITE_NAME}"
            body = f"""Hello,

Your payment for "{order.product.title}" has been confirmed.

Order ID: #{order.id}
Amount: ${order.amount_usd:.2f}

You can download your product from your dashboard:
{SITE_URL}/dashboard

Thank you for shopping with {SITE_NAME}!
"""
            send_email(order.user.email, subject, body)
        except Exception as e:
            print(f"Email error (ignored): {e}")

    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/order/{order_id}/add-credit")
async def add_as_credit(order_id: int, user=Depends(require_admin), db: Session = Depends(get_db)):
    """Add as Credit → money goes into customer Store Credit balance"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if order and order.status == "pending":
        buyer = db.query(User).filter(User.id == order.user_id).first()
        if buyer:
            buyer.credits = (buyer.credits or 0) + order.amount_usd
            order.status = "credited"
            order.notes = (order.notes or "") + " | Added as Store Credit"
            db.commit()

            try:
                subject = f"Store Credit added – {SITE_NAME}"
                body = f"""Hello,

We have added ${order.amount_usd:.2f} to your Store Credit balance.

You can now use this credit to buy products on the store:
{SITE_URL}/dashboard

Thank you!
{SITE_NAME}
"""
                send_email(buyer.email, subject, body)
            except Exception as e:
                print(f"Email error (ignored): {e}")

    return RedirectResponse("/admin", status_code=303)


@app.get("/health")
def health():
    return {"status": "healthy", "site": SITE_NAME}
