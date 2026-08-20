"""Artikel – ein Ordner mit Spezifikation.

Der Artikel trägt seine Stammdaten und die Erfassungsmaske der Datenerfassung. Er trägt
**keine Menge und keinen Bestand**: was es von ihm gibt, sind seine Instanzen, und deren
Menge ist die Anzahl ihrer Einzelinstanzen.

Entfallen sind mit der Prozesslogik: Freigabe-Gate, Einstandspreis und Durchlaufzeit
(beide aus abgeschlossenen Aufträgen abgeleitet) sowie das aufsummierte Gewicht (aus
verbauten Ressourcen).

**Ausser Betrieb nehmen ist ein Statuswechsel und sonst nichts** – ``PATCH`` mit
``status``, in beide Richtungen. Es gibt dafür keinen eigenen Endpunkt und keine
Wirkungsanalyse in einem Dialog: was ein Ausserbetriebnehmen anrichtet, steht als
**Auskunft am Datensatz** (``bom``) und ist damit immer sichtbar, nicht nur dem, der
klickt. **Ersetzen** wiederum ist keine Aktion am Vorgänger, sondern eine Angabe an der
**Anlage des Nachfolgers** (``ArticleCreate.replaces_object_id``).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, UserProfile
from ..schemas.article import (
    ArticleBom, ArticleLink, ArticleProcess, ArticleProcessStepResponse,
    ArticleCreate, ArticleNameSuggestion, ArticleResponse, ArticleUpdate, ArticleValidation,
    RetiredInput,
)
from ..schemas.instance import ArticleStock, InstanceSummary, stock_states
from ..services import article_names
from ..services import article_process as tpl_svc
from ..services import articles as articles_svc
from ..services import bom as bom_svc
from ..services import instances as inst_svc
from ..services.admin import log_audit
from ..services.lifecycle import ensure_version

router = APIRouter(prefix="/api/v1/erp/articles", tags=["articles"])


def _out(article: Article) -> ArticleResponse:
    """Die Antwort **ohne** Kette und Stückliste – für Feed und Schreibpfade.

    Die Stückliste kostet Abfragen; im Feed wären es zweihundertmal welche. ``bom``
    bleibt darum ``None``, und das heisst «nicht geladen» – nicht «nichts gefunden».

    **Auch die Schreibpfade antworten so.** Das Umfeld eines Artikels (wen löse ich ab,
    wer verbaut mich, was fehlt mir) ist eine eigene Frage mit einer eigenen Antwort, und
    die stellt die Oberfläche, wenn sie den Datensatz öffnet – am ``GET``. Sie hier
    mitzuliefern hiesse, sie zweimal zu rechnen und trotzdem nur an den Stellen zu haben,
    an denen zufällig gerade geschrieben wurde.
    """
    return ArticleResponse.model_validate(article)


def _link(article: Article | None) -> ArticleLink | None:
    """Einen Artikel so nennen, wie eine andere Antwort ihn nennt: Nummer · Name · Zustand."""
    if article is None or article.object_id is None:
        return None
    return ArticleLink(object_id=article.object_id, name=article.name, status=article.status)


def _ref(ref: bom_svc.ArticleRef) -> ArticleLink:
    return ArticleLink(object_id=ref.object_id, name=ref.name, status=ref.status)


def _detail(db: Session, article: Article) -> ArticleResponse:
    """Die Antwort **mit** Kette und Stückliste – nur am Detail.

    Beides sind Auskünfte über die **Umgebung** des Artikels: wen er ablöst, wer ihn
    ablöst, wer ihn verbaut, was in ihm ausser Betrieb ist. Sie stehen am Datensatz und
    nicht in einem Dialog – ein Dialog zeigt sie einmal, dem, der klickt; der Datensatz
    zeigt sie immer, allen.
    """
    out = _out(article)
    out.replaces = _link(articles_svc.predecessor_of(db, article))
    chain = articles_svc.chain_of(db, article)
    out.replaced_by = _link(chain[0]) if chain else None
    out.bom = ArticleBom(
        used_in=[_ref(r) for r in bom_svc.used_in(db, article)],
        retired_inputs=[
            RetiredInput(article=_ref(r.article), via=[_ref(v) for v in r.via],
                         replaced_by=_ref(r.replaced_by) if r.replaced_by else None)
            for r in bom_svc.retired_inputs(db, article)
        ],
    )
    return out


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
    # Die Ersetzung wird beim **Vorgänger** protokolliert: dort ist sie die Änderung, und
    # dort sucht sie jemand, der wissen will, warum ein Artikel ausser Betrieb ging.
    if data.replaces_object_id:
        log_audit(db, "articles", "replaced_by", str(article.object_id),
                  user_id=user.id, object_id=data.replaces_object_id)
    db.commit()
    db.refresh(article)
    return _out(article)


@router.get("/{object_id}", response_model=ArticleResponse)
def get_article(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return _detail(db, _get(db, object_id))


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


@router.get("/{object_id}/stock", response_model=ArticleStock)
def article_stock(
    object_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """**Wie viel habe ich von diesem Artikel, in welchem Zustand, unter welcher Nummer?**

    Eine Frage, ein Endpunkt. Der Vorgänger (``/instances``) lieferte nur eine Liste von
    Instanzen und war dabei kaputt: er las ``Instance.status``, eine Spalte, die es nicht
    gibt – die Instanz ist eine Gruppe und trägt keinen Zustand (Testnotiz #675). Jeder
    Aufruf endete mit 500, der Reiter «Bestand» war also nie zu sehen.

    Die **Aufstellung oben gilt für den ganzen Artikel**, die Liste darunter ist eine
    Seite. Sortiert wird **aufsteigend nach Objektnummer**: Nummern werden aufsteigend
    vergeben, und eine Instanz entsteht mit ihren Stücken – aufsteigend ist damit
    schlicht die Reihenfolge, in der das Material entstanden ist, also FIFO. Der Feed
    sortiert absteigend, weil man dort den zuletzt angelegten Datensatz sucht; hier sucht
    man das älteste Material, und das ist eine andere Frage.
    """
    from ..models import Instance  # lokal: der Artikel-Router kennt sonst kein Bestandsobjekt

    article = _get(db, object_id)
    mine = (Instance.article_id == article.id, Instance.is_active.is_(True))
    total_instances = db.query(func.count(Instance.id)).filter(*mine).scalar() or 0
    rows = (
        db.query(Instance)
        .filter(*mine)
        .order_by(Instance.object_id)
        .limit(limit)
        .offset(offset)
        .all()
    )
    by_instance = inst_svc.states(db, [i.id for i in rows])
    counts = inst_svc.article_states(db, article_id=article.id)
    return ArticleStock(
        states=stock_states(counts),
        total=sum(counts.values()),
        instance_total=int(total_instances),
        instances=[
            InstanceSummary(
                id=i.id, object_id=i.object_id, article_id=i.article_id,
                article_name=article.name, kind=i.kind, label=i.label,
                quantity=sum(by_instance.get(i.id, {}).values()),
                states=stock_states(by_instance.get(i.id, {})),
                created_at=i.created_at, updated_at=i.updated_at, is_active=i.is_active,
            )
            for i in rows
        ],
    )


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
