from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models_db import Hotel


def get_current_hotel(x_api_key: str = Header(...), db: Session = Depends(get_db)) -> Hotel:
    hotel = db.query(Hotel).filter(Hotel.api_key == x_api_key).first()
    if not hotel:
        raise HTTPException(status_code=401, detail="API key inválida")
    return hotel
