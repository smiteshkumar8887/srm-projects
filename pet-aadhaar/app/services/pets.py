import secrets
from pathlib import Path
from uuid import uuid4

import qrcode
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models


class PetNameExistsError(Exception):
    pass


def generate_aadhaar_id() -> str:
    return f"PAW-{secrets.token_hex(4).upper()}"


def pet_name_exists(db: Session, name: str, exclude_id: int | None = None) -> bool:
    query = db.query(models.Pet).filter(models.Pet.name.ilike(name.strip()))
    if exclude_id is not None:
        query = query.filter(models.Pet.id != exclude_id)
    return query.first() is not None


async def save_vaccination_file(file: UploadFile | None) -> tuple[str | None, str | None]:
    if not file or not file.filename:
        return None, None

    settings = get_settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix.lower() or ".bin"
    stored = f"{uuid4().hex}{suffix}"
    path = settings.upload_path / stored
    content = await file.read()
    path.write_bytes(content)
    return file.filename, str(path)


def generate_qr_for_pet(pet: models.Pet) -> str:
    settings = get_settings()
    settings.qr_path.mkdir(parents=True, exist_ok=True)
    public_url = f"{settings.base_url.rstrip('/')}/p/{pet.aadhaar_id}"
    img = qrcode.make(public_url)
    out = settings.qr_path / f"{pet.aadhaar_id}.png"
    img.save(out)
    return str(out)


def create_pet(
    db: Session,
    owner: models.User,
    *,
    name: str,
    breed: str,
    age_years: int,
    age_months: int,
    species: str,
    color: str | None,
    gender: str | None,
    notes: str | None,
    vaccination_filename: str | None,
    vaccination_path: str | None,
) -> models.Pet:
    if pet_name_exists(db, name):
        raise PetNameExistsError(f'Pet name "{name.strip()}" already exists.')

    pet = models.Pet(
        owner_id=owner.id,
        name=name.strip(),
        breed=breed.strip(),
        age_years=age_years,
        age_months=age_months,
        species=species.strip() or "Dog",
        color=(color or "").strip() or None,
        gender=(gender or "").strip() or None,
        notes=(notes or "").strip() or None,
        aadhaar_id=generate_aadhaar_id(),
        vaccination_filename=vaccination_filename,
        vaccination_path=vaccination_path,
    )
    db.add(pet)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PetNameExistsError(f'Pet name "{name.strip()}" already exists.') from exc

    db.refresh(pet)
    pet.qr_path = generate_qr_for_pet(pet)
    db.commit()
    db.refresh(pet)
    return pet


def update_pet(
    db: Session,
    pet: models.Pet,
    *,
    name: str,
    breed: str,
    age_years: int,
    age_months: int,
    species: str,
    color: str | None,
    gender: str | None,
    notes: str | None,
    vaccination_filename: str | None = None,
    vaccination_path: str | None = None,
) -> models.Pet:
    if pet_name_exists(db, name, exclude_id=pet.id):
        raise PetNameExistsError(f'Pet name "{name.strip()}" already exists.')

    pet.name = name.strip()
    pet.breed = breed.strip()
    pet.age_years = age_years
    pet.age_months = age_months
    pet.species = species.strip() or "Dog"
    pet.color = (color or "").strip() or None
    pet.gender = (gender or "").strip() or None
    pet.notes = (notes or "").strip() or None

    if vaccination_path:
        pet.vaccination_filename = vaccination_filename
        pet.vaccination_path = vaccination_path

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PetNameExistsError(f'Pet name "{name.strip()}" already exists.') from exc

    db.refresh(pet)
    pet.qr_path = generate_qr_for_pet(pet)
    db.commit()
    db.refresh(pet)
    return pet


def list_owner_pets(db: Session, owner_id: int) -> list[models.Pet]:
    return (
        db.query(models.Pet)
        .filter(models.Pet.owner_id == owner_id)
        .order_by(models.Pet.created_at.desc())
        .all()
    )


def get_owner_pet(db: Session, owner_id: int, pet_id: int) -> models.Pet | None:
    return (
        db.query(models.Pet)
        .filter(models.Pet.id == pet_id, models.Pet.owner_id == owner_id)
        .first()
    )


def get_pet_by_aadhaar(db: Session, aadhaar_id: str) -> models.Pet | None:
    return db.query(models.Pet).filter(models.Pet.aadhaar_id == aadhaar_id).first()
