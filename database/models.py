from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, validates  # Corrigido aqui
from datetime import datetime

# Criar a base do ORM
Base = declarative_base()

# Modelo Base para timestamps e ID automático
class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Modelo de Região (pode não ter UFs associadas)
class Regiao(BaseModel):
    __tablename__ = "regioes"

    nome = Column(String, nullable=False, unique=True)

    # Relacionamento com UF (Agora está aqui)
    ufs = relationship("UF", back_populates="regiao", cascade="all, delete-orphan")

    # Relacionamento com Dado (Uma Região pode ter vários Dados)
    dados = relationship("Dado", back_populates="regiao")

# Modelo de Unidade Federativa (UF sempre tem uma Região associada)
class UF(BaseModel):
    __tablename__ = "ufs"

    nome = Column(String, nullable=False, unique=True)
    sigla = Column(String(2), nullable=False, unique=True)
    regiao_id = Column(Integer, ForeignKey("regioes.id", ondelete="CASCADE"), nullable=False)

    # Relacionamento bidirecional com Região (UF obrigatoriamente pertence a uma Região)
    regiao = relationship("Regiao", back_populates="ufs")

    # Relacionamento com Dados (Uma UF pode ter vários dados)
    dados = relationship("Dado", back_populates="uf")

# Modelo de Produto
class Produto(BaseModel):
    __tablename__ = "produtos"

    nome = Column(String, nullable=False, unique=True)

    # Relacionamento com Dado (Um Produto pode ter vários Dados)
    dados = relationship("Dado", back_populates="produto")

# Modelo de Fonte
class Fonte(BaseModel):
    __tablename__ = "fontes"

    nome = Column(String, nullable=False, unique=True)
    url = Column(String, nullable=False, unique=True)

    # Relacionamento com Dado (Uma Fonte pode ter vários Dados)
    dados = relationship("Dado", back_populates="fonte")

    last_updated = Column(DateTime, nullable=True)

    def __init__(self, nome, url, created_at=None):
            """Permite que os timestamps sejam sobrescritos se fornecidos"""
            self.nome = nome
            self.url = url
            if created_at:
                self.created_at = created_at
            self.last_updated = None

    def set_last_updated(self, last_updated):
        self.last_updated = last_updated

# Modelo de Dado (Valor de um Produto em uma UF e Data)
class Dado(BaseModel):
    __tablename__ = "dados"

    data = Column(DateTime, nullable=False)
    valor = Column(Float, nullable=False)

    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    uf_id = Column(Integer, ForeignKey("ufs.id", ondelete="CASCADE"), nullable=True)  # UF é opcional
    regiao_id = Column(Integer, ForeignKey("regioes.id", ondelete="CASCADE"), nullable=True)  # Região é opcional
    fonte_id = Column(Integer, ForeignKey("fontes.id"), nullable=False)

    # Relacionamento bidirecional com Produto, UF, Região e Fonte
    produto = relationship("Produto", back_populates="dados")
    uf = relationship("UF", back_populates="dados")
    regiao = relationship("Regiao", back_populates="dados")  # Novo relacionamento com Região
    fonte = relationship("Fonte", back_populates="dados")

    @validates("regiao_id", "uf_id")
    def validate_regiao_uf_association(self, key, value):
        """Valida se não é fornecido tanto Região quanto UF no mesmo Dado."""
        if key == "uf_id" and value:
            if self.regiao_id:  # Se a Região já foi fornecida
                raise ValueError("Não é permitido fornecer Região e UF ao mesmo tempo.")
        elif key == "regiao_id" and value:
            if self.uf_id:  # Se a UF já foi fornecida
                raise ValueError("Não é permitido fornecer Região e UF ao mesmo tempo.")
        return value

# Criar a conexão com o banco SQLite
engine = create_engine("sqlite:///database/data.db")
Base.metadata.create_all(engine)