import os
import requests
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func, desc
from dotenv import load_dotenv
from models import db, User, Book, Review, ReadingStatus
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "bookhub-secret-dev-key-2024")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///bookhub.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "info"

GOOGLE_BOOKS_API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY", "")
GOOGLE_BOOKS_BASE_URL = "https://www.googleapis.com/books/v1/volumes"

HEADERS = {
    "User-Agent": "BookHub/1.0 (portfolio; python-requests)",
    "Accept": "application/json",
}


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def buscar_google_books(query, max_results=20):
    """Busca livros na Google Books API. Retorna lista de items ou [] em caso de erro."""
    if not GOOGLE_BOOKS_API_KEY:
        app.logger.warning("GOOGLE_BOOKS_API_KEY não configurada — busca desativada.")
        return []

    params = {
        "q": query,
        "maxResults": max_results,
        "printType": "books",
        "key": GOOGLE_BOOKS_API_KEY,
    }
    try:
        resp = requests.get(
            GOOGLE_BOOKS_BASE_URL,
            params=params,
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 403:
            app.logger.error("Google Books API: 403 Forbidden — verifique se a API Key é válida e se a Books API está ativada no Google Cloud Console.")
            return []
        if resp.status_code == 429:
            app.logger.error("Google Books API: cota excedida (429).")
            return []
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])
    except requests.exceptions.Timeout:
        app.logger.error("Google Books API: timeout.")
        return []
    except Exception as e:
        app.logger.error(f"Google Books API: erro inesperado — {e}")
        return []


def buscar_livro_por_id(google_id):
    """Busca detalhes de um livro pelo ID do Google Books."""
    if not GOOGLE_BOOKS_API_KEY:
        return None

    params = {"key": GOOGLE_BOOKS_API_KEY}
    try:
        resp = requests.get(
            f"{GOOGLE_BOOKS_BASE_URL}/{google_id}",
            params=params,
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code in (403, 404):
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        app.logger.error(f"buscar_livro_por_id({google_id}): {e}")
        return None


def buscar_livros_locais(query):
    """Busca nos livros já salvos no banco de dados (fallback offline)."""
    q = f"%{query}%"
    return Book.query.filter(
        db.or_(
            Book.titulo.ilike(q),
            Book.autor.ilike(q),
        )
    ).limit(20).all()


def salvar_ou_atualizar_livro(google_id):
    livro = Book.query.filter_by(google_books_id=google_id).first()
    if livro:
        return livro

    data = buscar_livro_por_id(google_id)
    if not data:
        return None

    info = data.get("volumeInfo", {})
    capa = info.get("imageLinks", {}).get("thumbnail", "")
    if capa:
        capa = capa.replace("http://", "https://")

    livro = Book(
        google_books_id=google_id,
        titulo=info.get("title", "Título desconhecido"),
        autor=", ".join(info.get("authors", ["Autor desconhecido"])),
        capa=capa,
        descricao=info.get("description", ""),
        ano=info.get("publishedDate", "")[:4] if info.get("publishedDate") else "",
        paginas=info.get("pageCount"),
        editora=info.get("publisher", ""),
        categorias=", ".join(info.get("categories", [])),
    )
    db.session.add(livro)
    db.session.commit()
    return livro


def formatar_resultado_google(item):
    info = item.get("volumeInfo", {})
    capa = info.get("imageLinks", {}).get("thumbnail", "")
    if capa:
        capa = capa.replace("http://", "https://")
    return {
        "google_id": item.get("id"),
        "titulo": info.get("title", "Sem título"),
        "autor": ", ".join(info.get("authors", ["Desconhecido"])),
        "capa": capa,
        "ano": info.get("publishedDate", "")[:4] if info.get("publishedDate") else "",
        "descricao": info.get("description", ""),
    }


# ──────────────────────────────────────────────
# ROTAS PÚBLICAS
# ──────────────────────────────────────────────

@app.route("/")
def home():
    # Últimas reviews com livro
    ultimas_reviews = (
        db.session.query(Review, Book, User)
        .join(Book, Review.book_id == Book.id)
        .join(User, Review.user_id == User.id)
        .order_by(desc(Review.data))
        .limit(6)
        .all()
    )

    # Livros mais avaliados (com média ≥ 3 e mais de 1 review)
    livros_populares = (
        db.session.query(
            Book,
            func.avg(Review.nota).label("media"),
            func.count(Review.id).label("total"),
        )
        .join(Review, Book.id == Review.book_id)
        .group_by(Book.id)
        .having(func.count(Review.id) >= 1)
        .order_by(desc(func.count(Review.id)))
        .limit(8)
        .all()
    )

    return render_template(
        "home.html",
        ultimas_reviews=ultimas_reviews,
        livros_populares=livros_populares,
    )


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        confirmar = request.form.get("confirmar_senha", "")

        if not nome or not email or not senha:
            flash("Preencha todos os campos.", "error")
            return render_template("cadastro.html")

        if senha != confirmar:
            flash("As senhas não coincidem.", "error")
            return render_template("cadastro.html")

        if len(senha) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "error")
            return render_template("cadastro.html")

        if User.query.filter_by(email=email).first():
            flash("E-mail já cadastrado.", "error")
            return render_template("cadastro.html")

        user = User(nome=nome, email=email)
        user.set_senha(senha)
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)
        flash(f"Bem-vindo ao BookHub, {nome}!", "success")
        return redirect(url_for("home"))

    return render_template("cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        lembrar = request.form.get("lembrar") == "on"

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_senha(senha):
            flash("E-mail ou senha incorretos.", "error")
            return render_template("login.html")

        login_user(user, remember=lembrar)
        next_page = request.args.get("next")
        flash(f"Bem-vindo de volta, {user.nome}!", "success")
        return redirect(next_page or url_for("home"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Até logo!", "info")
    return redirect(url_for("home"))


@app.route("/pesquisa")
def pesquisa():
    query = request.args.get("q", "").strip()
    resultados = []
    fonte = None
    sem_api_key = False

    if query:
        if not GOOGLE_BOOKS_API_KEY:
            sem_api_key = True
            livros_locais = buscar_livros_locais(query)
            resultados = [
                {"google_id": b.google_books_id, "titulo": b.titulo,
                 "autor": b.autor, "capa": b.capa, "ano": b.ano, "descricao": b.descricao}
                for b in livros_locais
            ]
            fonte = "local"
        else:
            items = buscar_google_books(query, max_results=20)
            if items:
                resultados = [formatar_resultado_google(item) for item in items]
                fonte = "google"
            else:
                livros_locais = buscar_livros_locais(query)
                resultados = [
                    {"google_id": b.google_books_id, "titulo": b.titulo,
                     "autor": b.autor, "capa": b.capa, "ano": b.ano, "descricao": b.descricao}
                    for b in livros_locais
                ]
                fonte = "local"

    return render_template("pesquisa.html", query=query, resultados=resultados,
                           fonte=fonte, sem_api_key=sem_api_key)


@app.route("/livro/<google_id>")
def livro(google_id):
    # Salva/recupera o livro do banco
    book = salvar_ou_atualizar_livro(google_id)
    if not book:
        flash("Livro não encontrado.", "error")
        return redirect(url_for("home"))

    media = book.get_media_nota()
    total_reviews = book.get_total_reviews()

    # Reviews com usuários
    reviews = (
        db.session.query(Review, User)
        .join(User, Review.user_id == User.id)
        .filter(Review.book_id == book.id)
        .order_by(desc(Review.data))
        .all()
    )

    # Status do usuário atual
    user_status = None
    user_review = None
    if current_user.is_authenticated:
        rs = ReadingStatus.query.filter_by(user_id=current_user.id, book_id=book.id).first()
        user_status = rs.status if rs else None
        user_review = Review.query.filter_by(user_id=current_user.id, book_id=book.id).first()

    return render_template(
        "livro.html",
        book=book,
        media=media,
        total_reviews=total_reviews,
        reviews=reviews,
        user_status=user_status,
        user_review=user_review,
        status_opcoes=ReadingStatus.STATUS_OPCOES,
    )


@app.route("/livro/<google_id>/status", methods=["POST"])
@login_required
def atualizar_status(google_id):
    book = salvar_ou_atualizar_livro(google_id)
    if not book:
        return jsonify({"error": "Livro não encontrado"}), 404

    novo_status = request.json.get("status")
    if novo_status not in ReadingStatus.STATUS_OPCOES:
        return jsonify({"error": "Status inválido"}), 400

    rs = ReadingStatus.query.filter_by(user_id=current_user.id, book_id=book.id).first()
    if rs:
        rs.status = novo_status
        rs.data_atualizacao = datetime.utcnow()
    else:
        rs = ReadingStatus(user_id=current_user.id, book_id=book.id, status=novo_status)
        db.session.add(rs)

    db.session.commit()
    return jsonify({"success": True, "status": novo_status})


@app.route("/livro/<google_id>/avaliar", methods=["POST"])
@login_required
def avaliar_livro(google_id):
    book = salvar_ou_atualizar_livro(google_id)
    if not book:
        return jsonify({"error": "Livro não encontrado"}), 404

    nota = request.json.get("nota")
    comentario = request.json.get("comentario", "").strip()

    if not nota or not isinstance(nota, int) or nota < 1 or nota > 5:
        return jsonify({"error": "Nota inválida (deve ser de 1 a 5)"}), 400

    review = Review.query.filter_by(user_id=current_user.id, book_id=book.id).first()
    if review:
        review.nota = nota
        review.comentario = comentario
        review.data = datetime.utcnow()
    else:
        review = Review(
            user_id=current_user.id,
            book_id=book.id,
            nota=nota,
            comentario=comentario,
        )
        db.session.add(review)

    db.session.commit()

    nova_media = book.get_media_nota()
    total = book.get_total_reviews()

    return jsonify({
        "success": True,
        "nova_media": nova_media,
        "total_reviews": total,
    })


@app.route("/perfil/<int:user_id>")
def perfil(user_id):
    user = User.query.get_or_404(user_id)
    stats = user.get_estatisticas()

    aba = request.args.get("aba", "avaliacoes")

    reviews = (
        db.session.query(Review, Book)
        .join(Book, Review.book_id == Book.id)
        .filter(Review.user_id == user.id)
        .order_by(desc(Review.data))
        .all()
    )

    def get_livros_por_status(status):
        return (
            db.session.query(ReadingStatus, Book)
            .join(Book, ReadingStatus.book_id == Book.id)
            .filter(ReadingStatus.user_id == user.id, ReadingStatus.status == status)
            .order_by(desc(ReadingStatus.data_atualizacao))
            .all()
        )

    lendo = get_livros_por_status("Lendo")
    quero_ler = get_livros_por_status("Quero Ler")
    concluidos = get_livros_por_status("Concluído")
    abandonados = get_livros_por_status("Abandonado")

    return render_template(
        "perfil.html",
        user=user,
        stats=stats,
        aba=aba,
        reviews=reviews,
        lendo=lendo,
        quero_ler=quero_ler,
        concluidos=concluidos,
        abandonados=abandonados,
    )


@app.route("/ranking")
def ranking():
    livros_ranking = (
        db.session.query(
            Book,
            func.avg(Review.nota).label("media"),
            func.count(Review.id).label("total"),
        )
        .join(Review, Book.id == Review.book_id)
        .group_by(Book.id)
        .having(func.count(Review.id) >= 1)
        .order_by(desc(func.avg(Review.nota)), desc(func.count(Review.id)))
        .limit(100)
        .all()
    )

    return render_template("ranking.html", livros_ranking=livros_ranking)


# ──────────────────────────────────────────────
# API JSON (para JS)
# ──────────────────────────────────────────────

@app.route("/api/pesquisa")
def api_pesquisa():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    if not GOOGLE_BOOKS_API_KEY:
        livros = buscar_livros_locais(query)
        return jsonify([
            {"google_id": b.google_books_id, "titulo": b.titulo,
             "autor": b.autor, "capa": b.capa, "ano": b.ano}
            for b in livros
        ])
    items = buscar_google_books(query, max_results=10)
    return jsonify([formatar_resultado_google(i) for i in items])


# ──────────────────────────────────────────────
# INICIALIZAÇÃO
# ──────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
