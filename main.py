from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal
from rutas_admin import router as rutas_admin, public_router as rutas_admin_public
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
app.include_router(rutas_admin_public)

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
            "mother_category_id": c.mother_category_id,
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
        mother_category_id=payload.mother_category_id,
    )
    return {
        "id": nueva.id_categoria,
        "name": nueva.nombre,
        "emoji": "",
        "userId": nueva.id_usuario,
        "mother_category_id": nueva.mother_category_id,
    }


@app.delete("/movements/{id_movement}")
def delete_movement(id_movement: str, db: Session = Depends(get_db)):
    result = crud.delete_movement(db=db, id_movement=id_movement)
    if result["ok"]:
        return {"ok": True, "tipo": result["tipo"]}
    raise HTTPException(status_code=404, detail="Movimiento no encontrado")


@app.delete("/categories/{id_categoria}")
def delete_category(id_categoria: str, db: Session = Depends(get_db)):
    result = crud.delete_categoria(db=db, id_categoria=id_categoria)
    if result["ok"]:
        return {"ok": True}

    if result["reason"] == "not_found":
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    if result["reason"] == "has_movements":
        partes = []
        if result["gastos"] > 0:
            partes.append(f"{result['gastos']} gasto(s)")
        if result["ingresos"] > 0:
            partes.append(f"{result['ingresos']} ingreso(s)")
        msg = (
            f"No se puede borrar la categoría porque tiene {' y '.join(partes)} "
            f"asociados. Borrá los movimientos primero."
        )
        raise HTTPException(status_code=400, detail=msg)

    raise HTTPException(status_code=400, detail="No se pudo borrar la categoría")


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
    except Exception as e:
        print("Error verificando token de Google:", repr(e))
        raise HTTPException(status_code=401, detail=f"Token de Google inválido: {e}")

    email = idinfo.get("email")
    nombre = idinfo.get("name") or (email.split("@")[0] if email else "Usuario")

    if not email:
        raise HTTPException(status_code=401, detail="Token sin email")

    try:
        usuario = crud.get_or_create_google_user(db, correo=email, nombre=nombre)
    except Exception as e:
        print("Error de BD en /auth/google:", repr(e))
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {e}")

    return {
        "id_usuario": usuario.id_usuario,
        "nombre": usuario.nombre,
        "correo": usuario.correo,
    }
