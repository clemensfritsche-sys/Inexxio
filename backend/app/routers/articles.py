"""Artikel – ein Ordner mit Spezifikation.

Der Artikel trägt seine Stammdaten und die Erfassungsmaske der Datenerfassung. Er trägt
**keine Menge und keinen Bestand**: was es von ihm gibt, sind seine Instanzen, und deren
Menge ist die Anzahl ihrer Einzelinstanzen.

Entfallen sind mit der Prozesslogik: Prozessschritte, Freigabe-Gate, Ersetzen samt
Wirkungsanalyse, Einstandspreis und Durchlaufzeit (beide aus abgeschlossenen Aufträgen
abgeleitet) sowie das aufsummierte Gewicht (aus verbauten Ressourcen).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, UserProfile
from ..schemas.article import (
    ArticleProcess, ArticleProcessStepResponse,
    ArticleCreate, ArticleNameSuggestion, ArticleResponse, ArticleUpdate, ArticleValidation,
)
from ..schemas.instance import InstanceSummary
from ..services import article_names
from ..services import article_process as tpl_svc
from ..services import articles as articles_svc
from ..services import instances as inst_svc
from ..services.admin import log_audit
from ..services.lifecycle import ensure_version

router = APIRouter(prefix="/api/v1/erp/articles", tags=["articles"])


def _out(article: Article) -> ArticleResponse:
    return ArticleResponse.model_validate(article)


def _get(db: Session, object_id: int) -> Article:
    article = db.query(Article).filter(Article.object_id == object_id).first()
    if article is None:
        raise HTTPException(status_code=404, detail=f"Artikel {object_id} nicht gefunden.")
    return article


@router.get("/name-suggestions", response_model=list[ArticleNameSuggestion])
def name_suggestions(
    q: str = Query("", description="Angefangener Name"),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Bereits verwendete oder ähnliche Namen – rein lexikalisch, ohne KI."""
    return article_names.suggest(db, q)


@router.get("", response_model=list[ArticleResponse])
def list_articles(
    search: str | None = Query(None),
    limit: int = Query(200, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    q = db.query(Article)
    if search and search.strip():
        q = q.filter(Article.name.ilike(f"%{search.strip()}%"))
    rows = q.order_by(Article.object_id.desc()).limit(limit).offset(offset).all()
    return [_out(a) for a in rows]


@router.post("/validate", response_model=ArticleValidation)
def validate_article(
    data: ArticleCreate,
    _db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Wäre dieser Entwurf freigebbar? Legt **nichts** an, zieht **keine** Nummer.

    Die Oberfläche fragt hier, statt die Regel nachzuformulieren: sonst gäbe es zwei
    Massstäbe für dieselbe Frage, und der schwächere entschiede, ob der Knopf leuchtet.
    """
    missing = articles_svc.validate_draft(data.model_dump())
    return ArticleValidation(saveable=not missing, missing=missing)


@router.post("", response_model=ArticleResponse, status_code=201)
def create_article(
    data: ArticleCreate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Anlegen **ist** Freigeben – ein Aufruf, eine Transaktion.

    Vorher entstand der Artikel per Autosave, sobald die Spezifikation stand: mit
    Objektnummer, aber ohne Prozess – ein Datensatz, der eine Zusage macht, die er nicht
    halten kann. Jetzt entsteht er erst, wenn **beides** da ist.
    """
    article = articles_svc.create_article(
        db, data.model_dump(exclude_unset=True), actor_id=user.id)
    log_audit(db, "articles", "release", article.name,
              user_id=user.id, object_id=article.object_id)
    db.commit()
    db.refresh(article)
    return _out(article)


@router.get("/{object_id}", response_model=ArticleResponse)
def get_article(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return _out(_get(db, object_id))


@router.patch("/{object_id}", response_model=ArticleResponse)
def update_article(
    object_id: int,
    data: ArticleUpdate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    article = _get(db, object_id)
    payload = data.model_dump(exclude_unset=True)
    ensure_version(article, payload.pop("expected_updated_at", None))

    for key, value in payload.items():
        if not hasattr(article, key):
            raise HTTPException(status_code=400, detail=f"Unbekanntes Feld «{key}».")
        before = getattr(article, key)
        if before == value:
            continue
        setattr(article, key, value)
        log_audit(db, "articles", key, str(value),
                  user_id=user.id, object_id=article.object_id, old_value=str(before))

    db.commit()
    db.refresh(article)
    return _out(article)


@router.get("/{object_id}/instances", response_model=list[InstanceSummary])
def article_instances(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Die Instanzen dieses Artikels – mit ihrer gezählten Menge."""
    from ..models import Instance  # lokal: der Artikel-Router kennt sonst kein Bestandsobjekt

    article = _get(db, object_id)
    rows = (
        db.query(Instance)
        .filter(Instance.article_id == article.id, Instance.is_active.is_(True))
        .order_by(Instance.object_id.desc())
        .all()
    )
    counts = inst_svc.quantities(db, [i.id for i in rows])
    return [
        InstanceSummary(
            id=i.id, object_id=i.object_id, article_id=i.article_id,
            article_name=article.name, kind=i.kind, status=i.status, label=i.label,
            quantity=counts.get(i.id, 0), created_at=i.created_at,
            updated_at=i.updated_at, is_active=i.is_active,
        )
        for i in rows
    ]


# ---------------------------------------------------------------------------
# Erzeugungsprozess – die Vorlage. Sie kann nichts ausführen (PROCESS_CORE.md §8.2):
# es gibt hier keinen Endpunkt, der ein Stück bewegt, und keinen Status zu setzen.
#
# Und sie lässt sich **nicht nachträglich ändern**: sie entsteht mit dem Artikel
# (``POST /erp/articles``) und ist ab da eingefroren. Ein «Modul hinzufügen»-Endpunkt
# wäre eine Tür in einen Datensatz, der bereits Aufträge speist – und die Kopien in
# laufenden Aufträgen trügen einen Stempel, der nicht mehr stimmt.
# ---------------------------------------------------------------------------

@router.get("/{object_id}/process", response_model=ArticleProcess)
def get_process(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    article = _get(db, object_id)
    return ArticleProcess(
        version=int(article.process_version or 0),
        steps=[
            ArticleProcessStepResponse.model_validate(s)
            for s in tpl_svc.steps_of(db, article)
        ],
    )
