from pydantic import BaseModel, EmailStr, Field
from datetime import date
from typing import Optional

class UserCreate(BaseModel):
    nom: str
    prenom: str
    date_naissance: date
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: Optional[int] = None
    nom: str
    prenom: str
    email: EmailStr
    date_inscription: Optional[date] = None
    
    class Config:
        from_attributes = True
