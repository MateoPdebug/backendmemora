from pydantic import BaseModel, EmailStr
from datetime import datetime
from decimal import Decimal
from typing import Optional


class UsuarioCreate(BaseModel):
    nombre: str
    correo: EmailStr
    contrasena: str


class UsuarioResponse(BaseModel):
    id_usuario: int
    nombre: str
    correo: EmailStr

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    correo: EmailStr
    contrasena: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class CategoriaCreate(BaseModel):
    nombre: str
    id_usuario: int
    es_predeterminada: bool = False


class MovimientoCreate(BaseModel):
    # monto<0 → gasto (guarda abs); monto>0 → ingreso.
    id_usuario: int
    id_categoria: str
    monto: Decimal
    descripcion: str = ""
    fecha: Optional[datetime] = None


class PresupuestoUpsert(BaseModel):
    id_usuario: int
    mes: str  # "YYYY-MM"
    monto: Decimal


class ForgotPasswordRequest(BaseModel):
    correo: EmailStr


class ResetPasswordRequest(BaseModel):
    correo: EmailStr
    codigo: str
    nueva_contrasena: str
