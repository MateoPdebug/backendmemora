from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal
import models

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

public_router = APIRouter(tags=["Admin Public"])


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
            "email": u.correo,
        }
        for u in usuarios
    ]


@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    total_ingresos = db.query(func.sum(models.Ingreso.monto)).scalar() or 0
    total_gastos = db.query(func.sum(models.Gasto.monto)).scalar() or 0
    total_usuarios = db.query(models.Usuario).count()

    return {
        "total_users": total_usuarios,
        "total_income": float(total_ingresos),
        "total_expenses": float(total_gastos),
    }


@public_router.get("/mother-categories")
def get_mother_categories(db: Session = Depends(get_db)):
    rows = (
        db.query(models.MotherCategory)
        .order_by(models.MotherCategory.id_mother_category)
        .all()
    )
    return [
        {"id": r.id_mother_category, "nombre": r.nombre}
        for r in rows
    ]


@public_router.get("/all-categories")
def get_all_categories(db: Session = Depends(get_db)):
    rows = db.query(models.Categoria).all()
    return [
        {
            "id_categoria": c.id_categoria,
            "nombre": c.nombre,
            "id_usuario": c.id_usuario,
            "es_predeterminada": c.es_predeterminada,
            "mother_category_id": c.mother_category_id,
        }
        for c in rows
    ]


@public_router.get("/analytics/category-distribution")
def category_distribution(db: Session = Depends(get_db)):
    result = (
        db.query(
            models.MotherCategory.id_mother_category,
            models.MotherCategory.nombre,
            func.coalesce(func.sum(models.Gasto.monto), 0).label("total"),
        )
        .outerjoin(
            models.Categoria,
            models.Categoria.mother_category_id == models.MotherCategory.id_mother_category,
        )
        .outerjoin(
            models.Gasto,
            models.Gasto.id_categoria == models.Categoria.id_categoria,
        )
        .group_by(
            models.MotherCategory.id_mother_category,
            models.MotherCategory.nombre,
        )
        .order_by(models.MotherCategory.id_mother_category)
        .all()
    )
    return [
        {"id": row[0], "nombre": row[1], "total": float(row[2])}
        for row in result
    ]
