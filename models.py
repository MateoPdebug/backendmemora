from sqlalchemy import (
    Column,
    String,
    Integer,
    DECIMAL,
    Boolean,
    TIMESTAMP,
    ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    correo = Column(String(200), unique=True, nullable=False)
    contrasena = Column(String(255), nullable=False)
    fecha_creacion = Column(TIMESTAMP, server_default=func.current_timestamp())

    categorias = relationship("Categoria", back_populates="usuario")
    gastos = relationship("Gasto", back_populates="usuario")
    ingresos = relationship("Ingreso", back_populates="usuario")
    presupuestos = relationship("PresupuestoMensual", back_populates="usuario")


class CategoriaPredefinida(Base):
    __tablename__ = "categorias_prede"

    id_categoria_prede = Column(String(36), primary_key=True)
    nombre = Column(String(50), unique=True, nullable=False)
    descripcion = Column(String(100), nullable=False)
    icono = Column(String(50), nullable=True)


class MotherCategory(Base):
    __tablename__ = "mother_categories"

    id_mother_category = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)

    categorias = relationship(
        "Categoria",
        back_populates="mother_category"
    )


class Categoria(Base):
    __tablename__ = "categorias"

    id_categoria = Column(String(36), primary_key=True)
    nombre = Column(String(50), nullable=False)
    id_usuario = Column(
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    es_predeterminada = Column(Boolean, nullable=False, default=False)

    mother_category_id = Column(
        Integer,
        ForeignKey(
        "mother_categories.id_mother_category",
        ondelete="SET NULL",
        onupdate="CASCADE"
        ),
        nullable=True,
    )

    fecha_creacion = Column(TIMESTAMP, server_default=func.current_timestamp())

    usuario = relationship("Usuario", back_populates="categorias")

    mother_category = relationship(
    "MotherCategory",
    back_populates="categorias"
    )

    gastos = relationship("Gasto", back_populates="categoria")
    ingresos = relationship("Ingreso", back_populates="categoria")


class Gasto(Base):
    __tablename__ = "gastos"

    id_gasto = Column(String(36), primary_key=True)
    monto = Column(DECIMAL(10, 2), nullable=False)
    descripcion = Column(String(150), nullable=False)
    fecha = Column(TIMESTAMP, server_default=func.current_timestamp())
    id_usuario = Column(
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    id_categoria = Column(
        String(36),
        ForeignKey("categorias.id_categoria", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )

    usuario = relationship("Usuario", back_populates="gastos")
    categoria = relationship("Categoria", back_populates="gastos")


class Ingreso(Base):
    __tablename__ = "ingresos"

    id_ingreso = Column(String(36), primary_key=True)
    monto = Column(DECIMAL(10, 2), nullable=False)
    descripcion = Column(String(150), nullable=False)
    fecha = Column(TIMESTAMP, server_default=func.current_timestamp())
    id_usuario = Column(
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    id_categoria = Column(
        String(36),
        ForeignKey("categorias.id_categoria", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )

    usuario = relationship("Usuario", back_populates="ingresos")
    categoria = relationship("Categoria", back_populates="ingresos")


class PresupuestoMensual(Base):
    __tablename__ = "presupuesto_mensual"

    id_presupuesto = Column(String(36), primary_key=True)
    id_usuario = Column(
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    mes = Column(String(15), nullable=False)
    monto = Column(DECIMAL(10, 2), nullable=False)
    fecha_creacion = Column(TIMESTAMP, server_default=func.current_timestamp())

    usuario = relationship("Usuario", back_populates="presupuestos")


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id_reset = Column(String(36), primary_key=True)
    id_usuario = Column(
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    codigo = Column(String(6), nullable=False)
    expira = Column(TIMESTAMP, nullable=False)
    usado = Column(Boolean, nullable=False, default=False)
    fecha_creacion = Column(TIMESTAMP, server_default=func.current_timestamp())
