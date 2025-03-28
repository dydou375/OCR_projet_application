from pydantic import BaseModel, EmailStr
from datetime import date
from typing import Optional

# Modèles pour les utilisateurs

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


from pydantic import BaseModel, Field
from typing import List, Dict, Any

# Modèles Pydantic pour les requêtes et réponses

class InvoiceItem(BaseModel):
    name: str
    quantity: int
    unit_price: float

class Invoice(BaseModel):
    filename: str
    data: Dict[str, Any] = Field(
        ...,
        example={
            "email": "client@example.com",
            "client": "Nom du client",
            "address": "Adresse du client",
            "invoice_number": "INV-12345",
            "issue_date": "2023-10-01",
            "total": 100.0,
            "items": [
                {"name": "Article 1", "quantity": 2, "unit_price": 25.0},
                {"name": "Article 2", "quantity": 1, "unit_price": 50.0}
            ]
        }
    )

class InvoiceResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class OCRServiceResponse(BaseModel):
    success: bool
    services: List[str]

class UserRegistrationResponse(BaseModel):
    success: bool
    message: str