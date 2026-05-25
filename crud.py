from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
import uuid
import random
import models


def get_usuario_by_correo(db: Session, correo: str):
    return db.query(models.Usuario).filter(models.Usuario.correo == correo).first()

def create_usuario(db: Session, nombre: str, correo: str, contrasena: str):
    nuevo_usuario = models.Usuario(
        nombre=nombre,
        correo=correo,
        contrasena=contrasena,
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario

def login_usuario(db: Session, correo: str, contrasena: str):
    return db.query(models.Usuario).filter(
        models.Usuario.correo == correo,
        models.Usuario.contrasena == contrasena,
    ).first()


def get_or_create_google_user(db: Session, correo: str, nombre: str):
    # Vincula por correo: si ya existía cuenta email/password se reusa.
    usuario = db.query(models.Usuario).filter(
        models.Usuario.correo == correo
    ).first()
    if usuario:
        return usuario

    nuevo = models.Usuario(
        nombre=nombre or correo.split("@")[0],
        correo=correo,
        contrasena=None,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


def get_categorias_by_user(db: Session, id_usuario: int):
    return db.query(models.Categoria).filter(
        models.Categoria.id_usuario == id_usuario
    ).order_by(models.Categoria.fecha_creacion.asc()).all()

def create_categoria(
    db: Session,
    id_usuario: int,
    nombre: str,
    es_predeterminada: bool = False,
):
    nueva = models.Categoria(
        id_categoria=str(uuid.uuid4()),
        nombre=nombre,
        id_usuario=id_usuario,
        es_predeterminada=es_predeterminada,
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


def get_gastos_by_user(db: Session, id_usuario: int):
    return db.query(models.Gasto).filter(
        models.Gasto.id_usuario == id_usuario
    ).order_by(models.Gasto.fecha.desc()).all()

def create_gasto(
    db: Session,
    id_usuario: int,
    id_categoria: str,
    monto: Decimal,
    descripcion: str,
    fecha: Optional[datetime] = None,
):
    nuevo = models.Gasto(
        id_gasto=str(uuid.uuid4()),
        id_usuario=id_usuario,
        id_categoria=id_categoria,
        monto=monto,
        descripcion=descripcion or "",
        fecha=fecha,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


def get_ingresos_by_user(db: Session, id_usuario: int):
    return db.query(models.Ingreso).filter(
        models.Ingreso.id_usuario == id_usuario
    ).order_by(models.Ingreso.fecha.desc()).all()

def create_ingreso(
    db: Session,
    id_usuario: int,
    id_categoria: str,
    monto: Decimal,
    descripcion: str,
    fecha: Optional[datetime] = None,
):
    nuevo = models.Ingreso(
        id_ingreso=str(uuid.uuid4()),
        id_usuario=id_usuario,
        id_categoria=id_categoria,
        monto=monto,
        descripcion=descripcion or "",
        fecha=fecha,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


def get_presupuesto(db: Session, id_usuario: int, mes: str):
    return db.query(models.PresupuestoMensual).filter(
        models.PresupuestoMensual.id_usuario == id_usuario,
        models.PresupuestoMensual.mes == mes,
    ).first()

RESET_CODE_TTL_MINUTES = 5


def create_password_reset(db: Session, id_usuario: int) -> models.PasswordReset:
    # Invalidamos códigos previos del usuario para que solo el último sirva.
    db.query(models.PasswordReset).filter(
        models.PasswordReset.id_usuario == id_usuario,
        models.PasswordReset.usado == False,  # noqa: E712
    ).update({"usado": True})

    codigo = f"{random.randint(0, 999999):06d}"
    reset = models.PasswordReset(
        id_reset=str(uuid.uuid4()),
        id_usuario=id_usuario,
        codigo=codigo,
        expira=datetime.utcnow() + timedelta(minutes=RESET_CODE_TTL_MINUTES),
        usado=False,
    )
    db.add(reset)
    db.commit()
    db.refresh(reset)
    return reset


def consume_password_reset(
    db: Session, id_usuario: int, codigo: str
) -> Optional[models.PasswordReset]:
    # Devuelve el reset si código válido y no expirado. Lo marca como usado.
    reset = db.query(models.PasswordReset).filter(
        models.PasswordReset.id_usuario == id_usuario,
        models.PasswordReset.codigo == codigo,
        models.PasswordReset.usado == False,  # noqa: E712
    ).order_by(models.PasswordReset.fecha_creacion.desc()).first()

    if not reset:
        return None
    if reset.expira < datetime.utcnow():
        return None

    reset.usado = True
    db.commit()
    db.refresh(reset)
    return reset


def update_password(db: Session, id_usuario: int, nueva_contrasena: str):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.id_usuario == id_usuario
    ).first()
    if not usuario:
        return None
    usuario.contrasena = nueva_contrasena
    db.commit()
    db.refresh(usuario)
    return usuario


def reclassify_categoria(
    db: Session,
    id_categoria: str,
    mother_category_id: Optional[int],
):
    categoria = db.query(models.Categoria).filter(
        models.Categoria.id_categoria == id_categoria
    ).first()
    if not categoria:
        return None
    categoria.mother_category_id = mother_category_id
    db.commit()
    db.refresh(categoria)
    return categoria


def delete_user(db: Session, id_usuario: int) -> bool:
    usuario = db.query(models.Usuario).filter(
        models.Usuario.id_usuario == id_usuario
    ).first()
    if not usuario:
        return False
    db.delete(usuario)
    db.commit()
    return True


def get_activity_logs(db: Session, id_usuario: int):
    gastos = db.query(models.Gasto).filter(
        models.Gasto.id_usuario == id_usuario
    ).all()
    ingresos = db.query(models.Ingreso).filter(
        models.Ingreso.id_usuario == id_usuario
    ).all()

    logs = []
    for g in gastos:
        logs.append({
            "tipo": "gasto",
            "fecha": g.fecha.isoformat() if g.fecha else None,
            "descripcion": f"{g.descripcion or 'Sin descripción'} — ${float(g.monto):,.0f}",
            "monto": float(g.monto),
        })
    for i in ingresos:
        logs.append({
            "tipo": "ingreso",
            "fecha": i.fecha.isoformat() if i.fecha else None,
            "descripcion": f"{i.descripcion or 'Sin descripción'} — ${float(i.monto):,.0f}",
            "monto": float(i.monto),
        })

    logs.sort(key=lambda x: x["fecha"] or "", reverse=True)
    return logs


def upsert_presupuesto(db: Session, id_usuario: int, mes: str, monto: Decimal):
    existing = get_presupuesto(db, id_usuario, mes)
    if existing:
        existing.monto = monto
        db.commit()
        db.refresh(existing)
        return existing

    nuevo = models.PresupuestoMensual(
        id_presupuesto=str(uuid.uuid4()),
        id_usuario=id_usuario,
        mes=mes,
        monto=monto,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo
