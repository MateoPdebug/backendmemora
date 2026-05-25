from fastapi import APIRouter
from sqlalchemy.orm import Session
from fastapi import Depends
from sqlalchemy import func
from database import SessionLocal
import models

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/users")
def get_users(db: Session = Depends(get_db)):

    usuarios = db.query(models.Usuario).all()

    return [
        {
            "id": u.id_usuario,
            "full_name": u.nombre,
            "email": u.correo
        }
        for u in usuarios
    ]

@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db)):

    total_ingresos = db.query(
        func.sum(models.Ingreso.monto)
    ).scalar() or 0

    total_gastos = db.query(
        func.sum(models.Gasto.monto)
    ).scalar() or 0

    total_usuarios = db.query(
        models.Usuario
    ).count()

    return {
        "total_users": total_usuarios,
        "total_income": float(total_ingresos),
        "total_expenses": float(total_gastos),
    }