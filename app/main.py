from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app.database import Base, engine
import app.models  # creates tables

app = FastAPI(title="Kojo Content Store API")

# SERVE STATIC FILES AND TEMPLATES FOR THE BEAUTIFUL PAGES
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# THIS CREATES ALL TABLES ON STARTUP
Base.metadata.create_all(bind=engine)

# --- API ROUTES ---
from app.routers import user, product, auth
app.include_router(user.router, prefix="/api/users", tags=["users"])
app.include_router(product.router, prefix="/api/products", tags=["products"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


# --- WEB PAGES ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/products", response_class=HTMLResponse)
def products_page(request: Request):
    return templates.TemplateResponse("products.html", {"request": request})

@app.get("/health")
def health_check():
    return {"status": "healthy"}
