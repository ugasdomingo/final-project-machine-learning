import hashlib
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models_db import Account, Sede


def generate_api_key() -> str:
    return secrets.token_hex(32)


def hash_api_key(api_key: str) -> str:
    # SHA-256 directo: la key es un token aleatorio de 256 bits, no una
    # contraseña humana, así que no necesita salt ni hash lento.
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_current_account(x_api_key: str = Header(...), db: Session = Depends(get_db)) -> Account:
    account = (
        db.query(Account)
        .filter(Account.api_key_hash == hash_api_key(x_api_key))
        .first()
    )
    if not account:
        raise HTTPException(status_code=401, detail="API key inválida")
    return account


def get_account_sede(sede_id: int, account: Account, db: Session) -> Sede:
    sede = (
        db.query(Sede)
        .filter(Sede.id == sede_id, Sede.account_id == account.id)
        .first()
    )
    if not sede:
        raise HTTPException(status_code=404, detail="Sede no encontrada para esta cuenta")
    return sede
