"""Client CRUD + nested session creation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.db import get_db

router = APIRouter(prefix="/api/clients", tags=["clients"])


def _get_client_or_404(client_id: int, db: DbSession) -> models.Client:
    client = db.get(models.Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("", response_model=list[schemas.ClientRead])
def list_clients(db: DbSession = Depends(get_db)):
    return db.scalars(select(models.Client).order_by(models.Client.name)).all()


@router.post("", response_model=schemas.ClientRead, status_code=201)
def create_client(payload: schemas.ClientCreate, db: DbSession = Depends(get_db)):
    client = models.Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=schemas.ClientDetail)
def get_client(client_id: int, db: DbSession = Depends(get_db)):
    client = db.scalar(
        select(models.Client)
        .options(selectinload(models.Client.sessions))
        .where(models.Client.id == client_id)
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=schemas.ClientRead)
def update_client(
    client_id: int, payload: schemas.ClientUpdate, db: DbSession = Depends(get_db)
):
    client = _get_client_or_404(client_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, db: DbSession = Depends(get_db)):
    client = _get_client_or_404(client_id, db)
    db.delete(client)
    db.commit()


@router.post(
    "/{client_id}/sessions", response_model=schemas.SessionRead, status_code=201
)
def create_session(
    client_id: int, payload: schemas.SessionCreate, db: DbSession = Depends(get_db)
):
    _get_client_or_404(client_id, db)
    session = models.Session(client_id=client_id, **payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
