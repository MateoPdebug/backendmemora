from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal
from rutas_admin import router as rutas_admin
from google.oauth2 import id_token
from google.auth.transport import requests
from decimal import Decimal
from schemas import GoogleAuthRequest
from schemas import (
    UsuarioCreate,
    UsuarioResponse,
    LoginRequest,
    CategoriaCreate,
    MovimientoCreate,
    PresupuestoUpsert,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
import crud
import models
import email_service

app = FastAPI()

app.include_router(rutas_admin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "API Memora funcionando"}


@app.post("/register", response_model=UsuarioResponse)
def registrar_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    usuario_existente = crud.get_usuario_by_correo(db, usuario.correo)
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    nuevo_usuario = crud.create_usuario(
        db=db,
        nombre=usuario.nombre,
        correo=usuario.correo,
        contrasena=usuario.contrasena,
    )
    return nuevo_usuario


@app.post("/login", response_model=UsuarioResponse)
def login(usuario: LoginRequest, db: Session = Depends(get_db)):
    usuario_db = crud.login_usuario(db, usuario.correo, usuario.contrasena)
    if not usuario_db:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    return usuario_db


@app.get("/categories")
def get_categories(userId: int, db: Session = Depends(get_db)):
    categorias = crud.get_categorias_by_user(db, userId)
    return [
        {
            "id": c.id_categoria,
            "name": c.nombre,
            "emoji": "",
            "userId": c.id_usuario,
        }
        for c in categorias
    ]


@app.post("/categories")
def create_category(payload: CategoriaCreate, db: Session = Depends(get_db)):
    nueva = crud.create_categoria(
        db=db,
        id_usuario=payload.id_usuario,
        nombre=payload.nombre,
        es_predeterminada=payload.es_predeterminada,
    )
    return {
        "id": nueva.id_categoria,
        "name": nueva.nombre,
        "emoji": "",
        "userId": nueva.id_usuario,
    }


def _gasto_to_movement(g: models.Gasto) -> dict:
    return {
        "id": g.id_gasto,
        "userId": g.id_usuario,
        "categoryId": g.id_categoria,
        "amount": float(-g.monto),  # negativo: indica gasto
        "description": g.descripcion,
        "date": g.fecha.isoformat() if g.fecha else None,
    }


def _ingreso_to_movement(i: models.Ingreso) -> dict:
    return {
        "id": i.id_ingreso,
        "userId": i.id_usuario,
        "categoryId": i.id_categoria,
        "amount": float(i.monto),
        "description": i.descripcion,
        "date": i.fecha.isoformat() if i.fecha else None,
    }


@app.get("/movements")
def get_movements(userId: int, db: Session = Depends(get_db)):
    gastos = crud.get_gastos_by_user(db, userId)
    ingresos = crud.get_ingresos_by_user(db, userId)

    movimientos = (
        [_gasto_to_movement(g) for g in gastos]
        + [_ingreso_to_movement(i) for i in ingresos]
    )
    movimientos.sort(key=lambda m: m["date"] or "", reverse=True)
    return movimientos


@app.post("/movements")
def create_movement(payload: MovimientoCreate, db: Session = Depends(get_db)):
    # monto<0 → gasto; monto>0 → ingreso; ==0 → 400.
    if payload.monto == 0:
        raise HTTPException(status_code=400, detail="El monto no puede ser cero")

    if payload.monto < 0:
        nuevo = crud.create_gasto(
            db=db,
            id_usuario=payload.id_usuario,
            id_categoria=payload.id_categoria,
            monto=abs(payload.monto),
            descripcion=payload.descripcion,
            fecha=payload.fecha,
        )
        return _gasto_to_movement(nuevo)
    else:
        nuevo = crud.create_ingreso(
            db=db,
            id_usuario=payload.id_usuario,
            id_categoria=payload.id_categoria,
            monto=payload.monto,
            descripcion=payload.descripcion,
            fecha=payload.fecha,
        )
        return _ingreso_to_movement(nuevo)


def _budget_to_dict(b: models.PresupuestoMensual) -> dict:
    return {
        "id": b.id_presupuesto,
        "userId": b.id_usuario,
        "mes": b.mes,
        "monto": float(b.monto),
    }


@app.get("/budget")
def get_budget(userId: int, mes: str, db: Session = Depends(get_db)):
    presupuesto = crud.get_presupuesto(db, userId, mes)
    if not presupuesto:
        return None
    return _budget_to_dict(presupuesto)


@app.post("/budget")
def upsert_budget(payload: PresupuestoUpsert, db: Session = Depends(get_db)):
    if payload.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
    presupuesto = crud.upsert_presupuesto(
        db=db,
        id_usuario=payload.id_usuario,
        mes=payload.mes,
        monto=payload.monto,
    )
    return _budget_to_dict(presupuesto)


@app.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    usuario = crud.get_usuario_by_correo(db, payload.correo)

    # No revelamos si el correo existe (para no filtrar usuarios registrados).
    if not usuario:
        return {"ok": True}

    # Cuentas de Google (sin contraseña) no pueden recuperarla por este flujo.
    if not usuario.contrasena:
        raise HTTPException(
            status_code=400,
            detail="Esta cuenta usa Google. Ingresá con 'Continuar con Google'.",
        )

    reset = crud.create_password_reset(db, usuario.id_usuario)
    try:
        email_service.send_reset_code(
            to=usuario.correo,
            nombre=usuario.nombre,
            codigo=reset.codigo,
        )
    except Exception as e:
        print("Error enviando mail de reset:", repr(e))
        raise HTTPException(
            status_code=500,
            detail="No se pudo enviar el correo. Intentá de nuevo en un momento.",
        )

    return {"ok": True}


@app.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    if len(payload.nueva_contrasena) < 6:
        raise HTTPException(
            status_code=400,
            detail="La contraseña debe tener al menos 6 caracteres.",
        )

    usuario = crud.get_usuario_by_correo(db, payload.correo)
    if not usuario:
        raise HTTPException(status_code=400, detail="Código inválido o expirado.")

    if not usuario.contrasena:
        raise HTTPException(
            status_code=400,
            detail="Esta cuenta usa Google. Ingresá con 'Continuar con Google'.",
        )

    reset = crud.consume_password_reset(db, usuario.id_usuario, payload.codigo.strip())
    if not reset:
        raise HTTPException(status_code=400, detail="Código inválido o expirado.")

    crud.update_password(db, usuario.id_usuario, payload.nueva_contrasena)
    return {"ok": True}


GOOGLE_WEB_CLIENT_ID = "202593089915-qd4olpl3pc79us47p77qt4egh5c4vgvi.apps.googleusercontent.com"


@app.post("/auth/google")
def auth_google(
    payload: GoogleAuthRequest,
    db: Session = Depends(get_db)
):
    try:
        idinfo = id_token.verify_oauth2_token(
            payload.id_token,
            requests.Request(),
            GOOGLE_WEB_CLIENT_ID,
            clock_skew_in_seconds=60,
        )

        email = idinfo.get("email")
        nombre = idinfo.get("name") or (email.split("@")[0] if email else "Usuario")

        if not email:
            raise HTTPException(status_code=401, detail="Token sin email")

        usuario = crud.get_or_create_google_user(db, correo=email, nombre=nombre)

        return {
            "id_usuario": usuario.id_usuario,
            "nombre": usuario.nombre,
            "correo": usuario.correo,
        }

    except HTTPException:
        raise
    except Exception as e:
        print("Error /auth/google:", repr(e))
        raise HTTPException(
            status_code=401,
            detail=f"Token de Google inválido: {e}"
        )
# =====================================================
# ALL CATEGORIES
# =====================================================

@app.get("/all-categories")
def get_all_categories(
    db: Session = Depends(get_db)
):

    categorias = db.query(models.Categoria).all()

    return [
        {
            "id": c.id_categoria,
            "nombre": c.nombre,
            "id_usuario": c.id_usuario
        }
        for c in categorias
    ]


# =====================================================
# ACTIVITY LOGS (SIMULADOS)
# =====================================================

@app.get("/activity-logs/{user_id}")
def get_activity_logs(
    user_id: int,
    db: Session = Depends(get_db)
):

    gastos = crud.get_gastos_by_user(
        db,
        user_id
    )

    ingresos = crud.get_ingresos_by_user(
        db,
        user_id
    )

    logs = []

    for g in gastos:

        logs.append({
            "tipo": "gasto",
            "descripcion": g.descripcion,
            "fecha": g.fecha.isoformat()
        })

    for i in ingresos:

        logs.append({
            "tipo": "ingreso",
            "descripcion": i.descripcion,
            "fecha": i.fecha.isoformat()
        })

    logs.sort(
        key=lambda x: x["fecha"],
        reverse=True
    )

    return logs


# =====================================================
# DELETE USER
# =====================================================

@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db)
):

    usuario = db.query(models.Usuario).filter(
        models.Usuario.id_usuario == user_id
    ).first()

    if not usuario:

        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado"
        )

    db.query(models.Gasto).filter(
        models.Gasto.id_usuario == user_id
    ).delete()

    db.query(models.Ingreso).filter(
        models.Ingreso.id_usuario == user_id
    ).delete()

    db.query(models.Categoria).filter(
        models.Categoria.id_usuario == user_id
    ).delete()

    db.delete(usuario)

    db.commit()

    return {
        "message": "Usuario eliminado correctamente"
    }
@app.get("/analytics/category-distribution")
def category_distribution(
    db: Session = Depends(get_db)
):

    categorias = db.query(models.Categoria).all()

    total = len(categorias)

    if total == 0:
        return []

    conteo = {}

    for categoria in categorias:

        if categoria.mother_category:

            nombre = categoria.mother_category.nombre

        else:

            nombre = "Sin Clasificar"

        if nombre not in conteo:

            conteo[nombre] = 0

        conteo[nombre] += 1

    analytics = []

    for nombre, cantidad in conteo.items():

        analytics.append({
            "category": nombre,
            "total": cantidad,
            "percentage": round((cantidad / total) * 100, 1)
        })

    analytics.sort(
        key=lambda x: x["total"],
        reverse=True
    )

    return analytics

@app.get("/mother-categories")
def get_mother_categories(
    db: Session = Depends(get_db)
):

    categorias = db.query(
        models.MotherCategory
    ).all()

    return [
        {
            "id": c.id_mother_category,
            "nombre": c.nombre
        }
        for c in categorias
    ]

@app.put("/reclassify-category/{category_id}")
def reclassify_category(
    category_id: str,
    mother_category_id: int,
    db: Session = Depends(get_db)
):

    categoria = db.query(
        models.Categoria
    ).filter(
        models.Categoria.id_categoria == category_id
    ).first()

    if not categoria:

        raise HTTPException(
            status_code=404,
            detail="Categoría no encontrada"
        )

    mother = db.query(
        models.MotherCategory
    ).filter(
        models.MotherCategory.id_mother_category == mother_category_id
    ).first()

    if not mother:

        raise HTTPException(
            status_code=404,
            detail="Categoría madre no encontrada"
        )

    categoria.mother_category_id = mother_category_id

    db.commit()

    return {
        "message": "Categoría reclasificada correctamente"
    }