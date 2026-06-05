from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    avatar_url = db.Column(db.Text, nullable=True)

    reviews = db.relationship("Review", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    reading_statuses = db.relationship("ReadingStatus", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def get_estatisticas(self):
        total_reviews = self.reviews.count()
        media = 0.0
        if total_reviews > 0:
            soma = sum(r.nota for r in self.reviews.all())
            media = round(soma / total_reviews, 1)

        lendo = self.reading_statuses.filter_by(status="Lendo").count()
        concluidos = self.reading_statuses.filter_by(status="Concluído").count()
        quero_ler = self.reading_statuses.filter_by(status="Quero Ler").count()
        abandonados = self.reading_statuses.filter_by(status="Abandonado").count()

        return {
            "total_reviews": total_reviews,
            "media_nota": media,
            "lendo": lendo,
            "concluidos": concluidos,
            "quero_ler": quero_ler,
            "abandonados": abandonados,
        }

    def __repr__(self):
        return f"<User {self.email}>"


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    google_books_id = db.Column(db.String(50), unique=True, nullable=False)
    titulo = db.Column(db.Text, nullable=False)
    autor = db.Column(db.Text, nullable=True)
    capa = db.Column(db.Text, nullable=True)
    descricao = db.Column(db.Text, nullable=True)
    ano = db.Column(db.String(10), nullable=True)
    paginas = db.Column(db.Integer, nullable=True)
    editora = db.Column(db.Text, nullable=True)
    categorias = db.Column(db.Text, nullable=True)

    reviews = db.relationship("Review", backref="book", lazy="dynamic", cascade="all, delete-orphan")
    reading_statuses = db.relationship("ReadingStatus", backref="book", lazy="dynamic", cascade="all, delete-orphan")

    def get_media_nota(self):
        total = self.reviews.count()
        if total == 0:
            return 0.0
        soma = sum(r.nota for r in self.reviews.all())
        return round(soma / total, 1)

    def get_total_reviews(self):
        return self.reviews.count()

    def get_total_leitores(self):
        return self.reading_statuses.count()

    def __repr__(self):
        return f"<Book {self.titulo}>"


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    nota = db.Column(db.Integer, nullable=False)  # 1 a 5
    comentario = db.Column(db.Text, nullable=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "book_id", name="unique_user_book_review"),
    )

    def __repr__(self):
        return f"<Review user={self.user_id} book={self.book_id} nota={self.nota}>"


class ReadingStatus(db.Model):
    __tablename__ = "reading_statuses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="Quero Ler",
    )
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    STATUS_OPCOES = ["Quero Ler", "Lendo", "Concluído", "Abandonado"]

    __table_args__ = (
        db.UniqueConstraint("user_id", "book_id", name="unique_user_book_status"),
    )

    def __repr__(self):
        return f"<ReadingStatus user={self.user_id} book={self.book_id} status={self.status}>"
