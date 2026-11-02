from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.api.deps import get_current_user, get_optional_user
from app.core.config import get_settings
from app.db import models
from app.db.session import get_db, init_db
from app.services import auth as auth_service
from app.services.pets import (
    PetNameExistsError,
    create_pet,
    get_owner_pet,
    get_pet_by_aadhaar,
    list_owner_pets,
    save_vaccination_file,
    update_pet,
)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request,
        name,
        context or {},
        status_code=status_code,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    settings.qr_path.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="pawaadhaar_session",
        max_age=60 * 60 * 24 * 14,
    )
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    app.mount("/media/qr", StaticFiles(directory=str(settings.qr_path)), name="qr")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code in {303, 302} and exc.headers and "Location" in exc.headers:
            return RedirectResponse(exc.headers["Location"], status_code=exc.status_code)
        return HTMLResponse(
            content=f"<h1>{exc.status_code}</h1><p>{exc.detail}</p><p><a href='/'>Home</a></p>",
            status_code=exc.status_code,
        )

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, user: models.User | None = Depends(get_optional_user)):
        return render(request, "index.html", {"user": user, "app_name": settings.app_name})

    @app.get("/register", response_class=HTMLResponse)
    def register_page(
        request: Request,
        user: models.User | None = Depends(get_optional_user),
    ):
        if user:
            return RedirectResponse("/dashboard", status_code=303)
        return render(
            request,
            "auth/register.html",
            {"user": None, "error": None, "app_name": settings.app_name},
        )

    @app.post("/register")
    def register(
        request: Request,
        full_name: str = Form(...),
        email: str = Form(...),
        phone: str = Form(...),
        address: str = Form(""),
        password: str = Form(...),
        confirm_password: str = Form(...),
        db: Session = Depends(get_db),
    ):
        error = None
        if password != confirm_password:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif auth_service.get_user_by_email(db, email):
            error = "An account with this email already exists."

        if error:
            return render(
                request,
                "auth/register.html",
                {
                    "user": None,
                    "error": error,
                    "app_name": settings.app_name,
                    "form": {
                        "full_name": full_name,
                        "email": email,
                        "phone": phone,
                        "address": address,
                    },
                },
                status_code=400,
            )

        user = auth_service.create_user(
            db,
            full_name=full_name,
            email=email,
            phone=phone,
            password=password,
            address=address,
        )
        request.session["user_id"] = user.id
        return RedirectResponse("/dashboard", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_page(
        request: Request,
        user: models.User | None = Depends(get_optional_user),
    ):
        if user:
            return RedirectResponse("/dashboard", status_code=303)
        return render(
            request,
            "auth/login.html",
            {"user": None, "error": None, "app_name": settings.app_name},
        )

    @app.post("/login")
    def login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db),
    ):
        user = auth_service.authenticate_user(db, email, password)
        if not user:
            return render(
                request,
                "auth/login.html",
                {
                    "user": None,
                    "error": "Invalid email or password.",
                    "app_name": settings.app_name,
                    "email": email,
                },
                status_code=401,
            )
        request.session["user_id"] = user.id
        return RedirectResponse("/dashboard", status_code=303)

    @app.post("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/", status_code=303)

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(
        request: Request,
        user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        pets = list_owner_pets(db, user.id)
        return render(
            request,
            "pets/dashboard.html",
            {
                "user": user,
                "pets": pets,
                "app_name": settings.app_name,
                "success": request.query_params.get("success"),
            },
        )

    @app.get("/pets/new", response_class=HTMLResponse)
    def new_pet_page(
        request: Request,
        user: models.User = Depends(get_current_user),
    ):
        return render(
            request,
            "pets/form.html",
            {
                "user": user,
                "pet": None,
                "error": None,
                "app_name": settings.app_name,
                "mode": "create",
            },
        )

    @app.post("/pets/new")
    async def create_pet_route(
        request: Request,
        name: str = Form(...),
        breed: str = Form(...),
        species: str = Form("Dog"),
        age_years: int = Form(0),
        age_months: int = Form(0),
        color: str = Form(""),
        gender: str = Form(""),
        notes: str = Form(""),
        vaccination_certificate: UploadFile | None = File(None),
        user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        try:
            filename, filepath = await save_vaccination_file(vaccination_certificate)
            create_pet(
                db,
                user,
                name=name,
                breed=breed,
                age_years=age_years,
                age_months=age_months,
                species=species,
                color=color,
                gender=gender,
                notes=notes,
                vaccination_filename=filename,
                vaccination_path=filepath,
            )
            return RedirectResponse("/dashboard?success=created", status_code=303)
        except PetNameExistsError as exc:
            return render(
                request,
                "pets/form.html",
                {
                    "user": user,
                    "pet": {
                        "name": name,
                        "breed": breed,
                        "species": species,
                        "age_years": age_years,
                        "age_months": age_months,
                        "color": color,
                        "gender": gender,
                        "notes": notes,
                    },
                    "error": str(exc),
                    "app_name": settings.app_name,
                    "mode": "create",
                },
                status_code=400,
            )

    @app.get("/pets/{pet_id}/edit", response_class=HTMLResponse)
    def edit_pet_page(
        pet_id: int,
        request: Request,
        user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        pet = get_owner_pet(db, user.id, pet_id)
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")
        return render(
            request,
            "pets/form.html",
            {
                "user": user,
                "pet": pet,
                "error": None,
                "app_name": settings.app_name,
                "mode": "edit",
            },
        )

    @app.post("/pets/{pet_id}/edit")
    async def edit_pet_route(
        pet_id: int,
        request: Request,
        name: str = Form(...),
        breed: str = Form(...),
        species: str = Form("Dog"),
        age_years: int = Form(0),
        age_months: int = Form(0),
        color: str = Form(""),
        gender: str = Form(""),
        notes: str = Form(""),
        vaccination_certificate: UploadFile | None = File(None),
        user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        pet = get_owner_pet(db, user.id, pet_id)
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")

        try:
            filename, filepath = await save_vaccination_file(vaccination_certificate)
            update_pet(
                db,
                pet,
                name=name,
                breed=breed,
                age_years=age_years,
                age_months=age_months,
                species=species,
                color=color,
                gender=gender,
                notes=notes,
                vaccination_filename=filename,
                vaccination_path=filepath,
            )
            return RedirectResponse("/dashboard?success=updated", status_code=303)
        except PetNameExistsError as exc:
            return render(
                request,
                "pets/form.html",
                {
                    "user": user,
                    "pet": {
                        "id": pet.id,
                        "name": name,
                        "breed": breed,
                        "species": species,
                        "age_years": age_years,
                        "age_months": age_months,
                        "color": color,
                        "gender": gender,
                        "notes": notes,
                        "vaccination_filename": pet.vaccination_filename,
                        "aadhaar_id": pet.aadhaar_id,
                    },
                    "error": str(exc),
                    "app_name": settings.app_name,
                    "mode": "edit",
                },
                status_code=400,
            )

    @app.get("/pets/{pet_id}/tag", response_class=HTMLResponse)
    def pet_tag_page(
        pet_id: int,
        request: Request,
        user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        pet = get_owner_pet(db, user.id, pet_id)
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")
        return render(
            request,
            "pets/tag.html",
            {
                "user": user,
                "pet": pet,
                "owner": user,
                "app_name": settings.app_name,
            },
        )

    @app.get("/pets/{pet_id}/certificate")
    def download_certificate(
        pet_id: int,
        user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        pet = get_owner_pet(db, user.id, pet_id)
        if not pet or not pet.vaccination_path:
            raise HTTPException(status_code=404, detail="Certificate not found")
        path = Path(pet.vaccination_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Certificate file missing")
        return FileResponse(
            path,
            filename=pet.vaccination_filename or path.name,
        )

    @app.get("/p/{aadhaar_id}", response_class=HTMLResponse)
    def public_pet_profile(
        aadhaar_id: str,
        request: Request,
        db: Session = Depends(get_db),
        user: models.User | None = Depends(get_optional_user),
    ):
        pet = get_pet_by_aadhaar(db, aadhaar_id)
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")
        owner = db.get(models.User, pet.owner_id)
        return render(
            request,
            "pets/public.html",
            {
                "user": user,
                "pet": pet,
                "owner": owner,
                "app_name": settings.app_name,
            },
        )

    return app


app = create_app()
