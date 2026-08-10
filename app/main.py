from fastapi import FastAPI, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import os, shutil, uuid

from .database import engine, Base, get_db
from .models import User, Product, Order
from .auth import (
    get_password_hash, authenticate_user, create_access_token,
    get_current_user, require_user, require_admin
)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Kojo Tools Store")

# Static & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Ensure upload folder exists
UPLOAD_DIR = "app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

SITE_NAME = os.getenv("SITE_NAME", "Kojo Tools Store")
BITCOIN_ADDRESS = os.getenv("BITCOIN_ADDRESS", "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")


def create_admin_if_needed(db: Session):
    admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if not admin:
        admin = User(
            email=ADMIN_EMAIL,
            hashed_password=get_password_hash(ADMIN_PASSWORD),
            full_name="Administrator",
            is_admin=True
        )
        db.add(admin)
        db.commit()
        print(f"Admin created: {ADMIN_EMAIL}")


@app.on_event("startup")
def startup():
    db = next(get_db())
    create_admin_if_needed(db)
    db.close()


# ---------- Pages ----------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "site_name": SITE_NAME,
        "error": None
    })


@app.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "site_name": SITE_NAME,
            "error": "Invalid email or password"
        }, status_code=400)

    token = create_access_token({"sub": user.email})
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=60*60*24*7)
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("register.html", {
        "request": request,
        "site_name": SITE_NAME,
        "error": None
    })


@app.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "site_name": SITE_NAME,
            "error": "Email already registered"
        }, status_code=400)

    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name or email.split("@")[0]
    )
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


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user=Depends(require_user),
    db: Session = Depends(get_db)
):
    products = db.query(Product).filter(Product.is_active == True).order_by(Product.created_at.desc()).all()
    my_orders = db.query(Order).filter(Order.user_id == user.id).order_by(Order.created_at.desc()).all()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "site_name": SITE_NAME,
        "user": user,
        "products": products,
        "orders": my_orders,
        "bitcoin_address": BITCOIN_ADDRESS
    })


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    products = db.query(Product).order_by(Product.created_at.desc()).all()
    orders = db.query(Order).order_by(Order.created_at.desc()).limit(50).all()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "site_name": SITE_NAME,
        "user": user,
        "products": products,
        "orders": orders,
        "bitcoin_address": BITCOIN_ADDRESS
    })


@app.post("/admin/upload")
async def admin_upload(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    price_btc: float = Form(...),
    price_usd_approx: float = Form(0.0),
    category: str = Form("document"),
    file: UploadFile = File(None),
    user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    file_path = ""
    if file and file.filename:
        ext = os.path.splitext(file.filename)[1]
        unique_name = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_path = unique_name

    product = Product(
        title=title,
        description=description,
        price_btc=price_btc,
        price_usd_approx=price_usd_approx,
        category=category,
        file_path=file_path
    )
    db.add(product)
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/toggle/{product_id}")
async def toggle_product(
    product_id: int,
    user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.is_active = not product.is_active
        db.commit()
    return RedirectResponse("/admin", status_code=303)


@app.post("/buy/{product_id}")
async def buy_product(
    product_id: int,
    user=Depends(require_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    order = Order(
        user_id=user.id,
        product_id=product.id,
        amount_btc=product.price_btc,
        status="pending"
    )
    db.add(order)
    db.commit()
    return RedirectResponse(f"/order/{order.id}", status_code=303)


@app.get("/order/{order_id}", response_class=HTMLResponse)
async def order_page(
    order_id: int,
    request: Request,
    user=Depends(require_user),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return templates.TemplateResponse("order.html", {
        "request": request,
        "site_name": SITE_NAME,
        "user": user,
        "order": order,
        "bitcoin_address": BITCOIN_ADDRESS
    })


@app.post("/order/{order_id}/confirm")
async def confirm_payment(
    order_id: int,
    tx_id: str = Form(""),
    user=Depends(require_user),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.tx_id = tx_id
    order.status = "pending"  # still needs admin approval
    db.commit()
    return RedirectResponse(f"/order/{order.id}", status_code=303)


@app.post("/admin/order/{order_id}/mark-paid")
async def mark_paid(
    order_id: int,
    user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        order.status = "paid"
        order.paid_at = datetime.utcnow()
        db.commit()
    return RedirectResponse("/admin", status_code=303)


@app.get("/download/{order_id}")
async def download_file(
    order_id: int,
    user=Depends(require_user),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order or order.status != "paid":
        raise HTTPException(status_code=403, detail="Payment not confirmed")
    if not order.product.file_path:
        raise HTTPException(status_code=400, detail="No file for this product")

    path = os.path.join(UPLOAD_DIR, order.product.file_path)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File missing")
    return FileResponse(path, filename=order.product.title + os.path.splitext(path)[1])
