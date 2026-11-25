"""
Connexion aux sources externes utilisées après la formulation du problème (phases 8 à 10).

- Wiki de la Fabrique des Mobilités : Communs, Acteurs, Projets, Connaissances
  (API Semantic MediaWiki, User-Agent autorisé requis)
- France Mobilités : solutions et acteurs (flux JSON public)
- Données ouvertes : data.gouv.fr (jeux de données et API) et catalogue Melodi de l'INSEE

Principe commun : on télécharge (et met en cache) un index léger de chaque source,
on présélectionne localement les fiches qui contiennent les mots-clés du problème,
puis Claude classe les meilleures candidates (dans app.py).
"""

from __future__ import annotations

import html
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import requests
import streamlit as st

# ─── RÉGLAGES ────────────────────────────────────────────────────────────────────
WIKI_API = "https://wiki.lafabriquedesmobilites.fr/api.php"
WIKI_BASE = "https://wiki.lafabriquedesmobilites.fr/wiki/"
FM_API = "https://www.francemobilites.fr/api/v1/json/node/list/solution/all"
FM_BASE = "https://www.francemobilites.fr"
# Page d'origine du catalogue, indiquée en balise canonical (consigne de France Mobilités)
FM_SOLUTIONS_PAGE = "https://www.francemobilites.fr/solutions"
DATAGOUV_API = "https://www.data.gouv.fr/api/1/"
MELODI_CATALOG = "https://api.insee.fr/melodi/catalog/all"

CACHE_TTL = 24 * 3600  # les index sont rechargés au plus une fois par jour


def _wiki_user_agent() -> str:
    """Le wiki n'accepte les requêtes automatiques qu'avec un User-Agent autorisé."""
    try:
        return st.secrets.get("WIKI_USER_AGENT", "XD-Chatbot")
    except Exception:
        return "XD-Chatbot"


def _get_json(url: str, params: dict | None = None, headers: dict | None = None,
              timeout: int = 60, tries: int = 3):
    """GET JSON avec quelques nouvelles tentatives (les API publiques coupent parfois)."""
    err = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=headers or {}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{url} : {err}")


# ─── OUTILS TEXTE ────────────────────────────────────────────────────────────────
_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", text or ""))).strip()


def norm(text: str) -> str:
    """Minuscules, sans accents, ponctuation remplacée par des espaces."""
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " " + re.sub(r"[^a-z0-9]+", " ", t).strip() + " "


STOPWORDS = set("""a au aux avec ce ces dans de des du en et la le les leur leurs l d un une pour par
sur sous son sa ses ou ne pas plus moins tout tous toute toutes entre afin vers chez comme qui que quoi
dont est sont etre faire mieux tres via selon lors peu""".split())


def split_keywords(keywords: list[str]) -> list[str]:
    """Transforme des expressions en mots-clés simples utilisables par la recherche.

    « covoiturage domicile-travail en zone rurale » →
    ["covoiturage", "domicile travail", "domicile", "travail", "zone", "rurale"].
    Accepte aussi une chaîne unique séparée par des virgules, points-virgules ou retours à la ligne.
    """
    if isinstance(keywords, str):
        keywords = [keywords]
    raw = []
    for k in keywords:
        raw += [x.strip() for x in re.split(r"[,;\n]+", k or "") if x.strip()]
    out: list[str] = []

    def add(x):
        if x and x not in out:
            out.append(x)

    for k in raw:
        words = [w for w in norm(k).split() if len(w) >= 3 and w not in STOPWORDS]
        if not words:
            continue
        if len(words) <= 2:
            add(" ".join(words))          # expression courte gardée telle quelle
        # Mots composés (« domicile-travail ») gardés ensemble, puis chaque mot seul
        for part in re.split(r"\s+", k):
            sub = [w for w in norm(part).split() if len(w) >= 3 and w not in STOPWORDS]
            if len(sub) == 2:
                add(" ".join(sub))
        for w in words:
            add(w)
    return out


def score_record(rec: dict, keywords: list[str]) -> float:
    """Score simple : présence de chaque mot-clé, pondérée selon le champ où il apparaît.

    `rec["_idx"]` est un dict {nom_de_champ: (texte_normalisé, poids)}.
    """
    score = 0.0
    for kw in keywords:
        k = norm(kw)
        if len(k.strip()) < 3:
            continue
        best = 0.0
        for txt, w in rec["_idx"].values():
            if k in txt:
                best = max(best, w)
        # Une expression de plusieurs mots trouvée telle quelle compte davantage
        score += best * (1.5 if " " in k.strip() else 1.0)
    return score


def preselect(records: list[dict], keywords: list[str], n: int, min_score: float = 1.0,
              bonus: dict | None = None) -> list[dict]:
    """Garde les n fiches au meilleur score. `bonus` : {titre: points ajoutés}."""
    bonus = bonus or {}
    keywords = split_keywords(keywords)
    scored = [(score_record(r, keywords) + bonus.get(r.get("titre"), 0.0), r) for r in records]
    scored = [x for x in scored if x[0] >= min_score]
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for s, r in scored[:n]:
        r2 = {k: v for k, v in r.items() if k != "_idx"}
        r2["_score"] = s
        out.append(r2)
    return out


def _idx(**fields) -> dict:
    """Prépare l'index de recherche : nom_de_champ=(texte, poids)."""
    return {k: (norm(v[0]), v[1]) for k, v in fields.items()}


def slug_label(url_or_slug: str) -> str:
    """'/acteurs/mon-acteur' → 'Mon acteur'."""
    s = (url_or_slug or "").rstrip("/").split("/")[-1]
    s = s.replace("-", " ").strip()
    return s[:1].upper() + s[1:] if s else ""


# ════════════════════════════════════════════════════════════════════════════════
# WIKI DE LA FABRIQUE DES MOBILITÉS
# ════════════════════════════════════════════════════════════════════════════════
# Type de fiche → requête Semantic MediaWiki + attributs à récupérer
WIKI_TYPES = {
    "Commun": ("[[Category:Commun]]", ["ShortDescription", "Tags", "Theme", "CommunCategorie", "Acteur"]),
    "Projet": ("[[Category:Projet]]", ["ShortDescription", "Tags", "Theme", "Acteur", "Défi"]),
    "Acteur": ("[[Category:Acteur]]", ["Tags", "Theme"]),
    # Les « Connaissances » sont rangées dans la catégorie Référentiel avec TypePage=Connaissance
    "Connaissance": ("[[TypePage::Connaissance]]", ["Tags", "Theme", "Défi"]),
}


def _po_values(v) -> list[str]:
    """Valeurs d'un attribut SMW (texte ou page liée) → liste de textes."""
    out = []
    for x in v or []:
        if isinstance(x, dict):
            out.append(x.get("fulltext") or x.get("raw") or "")
        else:
            out.append(str(x))
    return [o for o in out if o]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def wiki_index() -> list[dict]:
    """Toutes les fiches Commun / Projet / Acteur / Connaissance du wiki (index léger)."""
    headers = {"User-Agent": _wiki_user_agent()}

    def fetch_type(item):
        wtype, (cond, props) = item
        records: list[dict] = []
        offset = 0
        while True:
            q = cond + "".join(f"|?{p}" for p in props) + f"|limit=500|offset={offset}"
            d = _get_json(WIKI_API, {"action": "ask", "query": q, "format": "json"}, headers)
            if "error" in d:
                raise RuntimeError(d["error"].get("info", str(d["error"])))
            for title, v in (d.get("query", {}).get("results") or {}).items():
                po = v.get("printouts", {})
                short = " ".join(_po_values(po.get("ShortDescription")))
                tags = _po_values(po.get("Tags"))
                themes = _po_values(po.get("Theme"))
                acteurs = _po_values(po.get("Acteur"))
                defis = _po_values(po.get("Défi"))
                records.append({
                    "type": wtype,
                    "titre": title,
                    "description": short,
                    "tags": tags,
                    "themes": themes,
                    "acteurs": acteurs,
                    "defis": defis,
                    "categories": _po_values(po.get("CommunCategorie")),
                    "url": v.get("fullurl") or WIKI_BASE + title.replace(" ", "_"),
                    "_idx": _idx(
                        titre=(title, 3.0),
                        description=(short, 2.0),
                        tags=(" ; ".join(tags), 2.0),
                        themes=(" ; ".join(themes + defis), 1.0),
                    ),
                })
            nxt = d.get("query-continue-offset")
            if not nxt:
                break
            offset = nxt
        return records

    with ThreadPoolExecutor(max_workers=4) as ex:
        return [r for recs in ex.map(fetch_type, WIKI_TYPES.items()) for r in recs]


def wiki_fulltext(keywords: list[str], limit: int = 30) -> dict[str, int]:
    """Recherche plein texte du wiki (corps des pages) → {titre: nb de requêtes trouvées}."""
    headers = {"User-Agent": _wiki_user_agent()}
    def one(kw):
        try:
            return _get_json(WIKI_API, {"action": "query", "list": "search", "srsearch": kw,
                                        "srlimit": limit, "srnamespace": 0, "format": "json"},
                             headers, timeout=30, tries=2)
        except RuntimeError:
            return {}

    hits: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for d in ex.map(one, split_keywords(keywords)[:6]):
            for x in d.get("query", {}).get("search", []):
                hits[x["title"]] = hits.get(x["title"], 0) + 1
    return hits


def wiki_candidates(keywords: list[str], per_type: int = 15) -> dict[str, list[dict]]:
    """Présélection par type de fiche, en combinant index sémantique et recherche plein texte."""
    records = wiki_index()
    # Bonus si la page ressort aussi en recherche plein texte (corps des pages)
    bonus = {t: 1.5 * c for t, c in wiki_fulltext(keywords).items()}
    out = {}
    for wtype in WIKI_TYPES:
        recs = [r for r in records if r["type"] == wtype]
        out[wtype] = preselect(recs, keywords, per_type, bonus=bonus)
    return out


# ════════════════════════════════════════════════════════════════════════════════
# FRANCE MOBILITÉS
# ════════════════════════════════════════════════════════════════════════════════
FM_THEMES = {
    "mobilite-partagee": "Mobilité partagée",
    "mobilite-pour-tous": "Mobilité pour tous",
    "connaissance-la-mobilite": "Connaissance de la mobilité",
    "amenagement-lespace-public-et-modes-actifs": "Aménagement de l'espace public et modes actifs",
    "transports-collectifs-et-optimisation-des-trafics-routiers": "Transports collectifs et optimisation des trafics routiers",
    "information-voyageur-et-billettique-multimodale": "Information voyageur et billettique multimodale",
    "logistique-urbaine-durable": "Logistique urbaine durable",
    "limiter-les-deplacements-subis": "Limiter les déplacements subis",
    "mobilite-routiere-automatisee-et-connectee": "Mobilité routière automatisée et connectée",
    "mobilite-et-energies-alternatives": "Mobilité et énergies alternatives",
}
FM_MATURITE = {"exploitation": "En exploitation", "experimental": "Expérimentation",
               "concept": "Concept", "idea": "Idée"}


def _fm_val(node: dict, field: str, key: str = "value"):
    v = node.get(field) or []
    return v[0].get(key) if v and isinstance(v[0], dict) else None


def _fm_terms(node: dict, field: str) -> list[str]:
    out = []
    for t in node.get(field) or []:
        url = t.get("url", "")
        slug = url.rstrip("/").split("/")[-1]
        out.append(FM_THEMES.get(slug) or slug_label(url))
    return out


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fm_index() -> list[dict]:
    """Toutes les solutions publiées sur francemobilites.fr (flux d'environ 15 Mo)."""
    nodes = _get_json(FM_API, timeout=120)
    records = []
    for n in nodes:
        if _fm_val(n, "status") is False:
            continue
        title = _fm_val(n, "title") or ""
        subtitle = strip_html(_fm_val(n, "field_subtitle") or "")
        body = strip_html(_fm_val(n, "body") or "")
        fonctionnement = strip_html(_fm_val(n, "field_body_1") or "")
        usagers = strip_html(_fm_val(n, "field_body_2") or "")
        themes = _fm_terms(n, "field_vocabulary_a")
        actor_url = _fm_val(n, "field_actor", "url") or ""
        alias = (n.get("path") or [{}])[0].get("alias") or f"/node/{_fm_val(n, 'nid')}"
        records.append({
            "id": str(_fm_val(n, "nid")),
            "titre": title,
            "sous_titre": subtitle,
            "description": body[:600],
            "themes": themes,
            "territoires": _fm_terms(n, "field_vocabulary_d"),
            "avec_acteurs": _fm_terms(n, "field_vocabulary_e"),
            "maturite": FM_MATURITE.get(_fm_val(n, "field_mature") or "", _fm_val(n, "field_mature") or ""),
            "porteur": slug_label(actor_url),
            "porteur_url": FM_BASE + actor_url if actor_url else "",
            "url": FM_BASE + alias,
            "maj": (_fm_val(n, "changed") or "")[:10],
            "_idx": _idx(
                titre=(title, 3.0),
                sous_titre=(subtitle, 2.5),
                themes=(" ; ".join(themes), 1.5),
                corps=(body + " " + fonctionnement + " " + usagers, 1.0),
            ),
        })
    return records


def fm_candidates(keywords: list[str], n: int = 30) -> list[dict]:
    return preselect(fm_index(), keywords, n)


# ════════════════════════════════════════════════════════════════════════════════
# DONNÉES OUVERTES : DATA.GOUV.FR + INSEE (MELODI)
# ════════════════════════════════════════════════════════════════════════════════
def simplify_queries(queries: list[str], max_words: int = 2) -> list[str]:
    """Requêtes courtes pour data.gouv.fr : la recherche exige que tous les mots soient présents,
    donc une requête longue ne renvoie souvent rien."""
    out = []
    for q in split_keywords(queries) if isinstance(queries, str) else queries:
        for part in re.split(r"[,;\n]+", q or ""):
            words = [w for w in re.split(r"\s+", part.strip())
                     if len(norm(w).strip()) >= 3 and norm(w).strip() not in STOPWORDS]
            if words:
                short = " ".join(words[:max_words])
                if short.lower() not in (o.lower() for o in out):
                    out.append(short)
    return out


def datagouv_search(queries: list[str], per_query: int = 8) -> list[dict]:
    """Recherche de jeux de données et d'API sur data.gouv.fr (API publique, sans clé)."""
    queries = simplify_queries(queries)
    jobs = [(q, kind, path) for q in queries[:6]
            for kind, path in (("Jeu de données", "datasets/"), ("API", "dataservices/"))]

    def one(job):
        q, kind, path = job
        try:
            return job, _get_json(DATAGOUV_API + path, {"q": q, "page_size": per_query}, timeout=30, tries=2)
        except RuntimeError:
            return job, {}

    seen, out = set(), []
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(one, jobs))
        # Repli : une requête de 2 mots sans résultat est relancée mot par mot
        empty = {q for (q, kind, _), d in results if kind == "Jeu de données" and not d.get("data") and " " in q}
        retry = [(w, "Jeu de données", "datasets/") for q in empty for w in q.split()
                 if len(w) >= 3 and w.lower() not in STOPWORDS]
        results += list(ex.map(one, retry))
    for (q, kind, _), d in results:
        for x in d.get("data", []):
            if x.get("id") in seen or x.get("archived") or x.get("deleted") or x.get("archived_at"):
                continue
            seen.add(x.get("id"))
            org = (x.get("organization") or {}).get("name") or ""
            formats = sorted({(r.get("format") or "").lower() for r in x.get("resources", []) if r.get("format")})
            out.append({
                "id": "dg_" + x["id"],
                "source": "data.gouv.fr",
                "type": kind,
                "titre": x.get("title", ""),
                "producteur": org,
                "description": strip_html(x.get("description_short") or x.get("description") or "")[:400],
                "url": x.get("page") or x.get("self_web_url") or "",
                "maj": (x.get("last_update") or x.get("metadata_modified_at") or "")[:10],
                "formats": ", ".join(formats[:5]),
                "vues": (x.get("metrics") or {}).get("views"),
                "requete": q,
            })
    return out


def _fr(value) -> str:
    """Texte français d'un champ multilingue Melodi."""
    if isinstance(value, list):
        for e in value:
            if isinstance(e, dict) and e.get("lang") == "fr":
                return e.get("content") or ""
        return ""
    return value or ""


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def melodi_index() -> list[dict]:
    """Catalogue des jeux de données de l'INSEE disponibles via l'API Melodi."""
    records = []
    for x in _get_json(MELODI_CATALOG, timeout=90):
        ident = x.get("identifier", "")
        title = _fr(x.get("title"))
        desc = strip_html(_fr(x.get("description")))
        kw = " ; ".join(_fr(k.get("label")) if isinstance(k, dict) else str(k)
                        for k in (x.get("keyword") or []))
        t = x.get("temporal") or {}
        records.append({
            "id": "insee_" + ident,
            "source": "INSEE (Melodi)",
            "type": "Jeu de données",
            "titre": title,
            "producteur": "INSEE",
            "description": desc[:400],
            "url": "https://catalogue-donnees.insee.fr/fr/catalogue/recherche/" + ident,
            "maj": (x.get("modified") or "")[:10],
            "periode": f"{(t.get('startPeriod') or '')[:4]}–{(t.get('endPeriod') or '')[:4]}".strip("–"),
            "echelles": ", ".join(dict.fromkeys(z.get("id", "") for z in x.get("spatialResolution") or [])),
            "_idx": _idx(titre=(title, 3.0), mots_cles=(kw, 2.0), description=(desc, 1.0)),
        })
    return records


def opendata_candidates(queries: list[str], keywords: list[str]) -> tuple[list[dict], list[str]]:
    """Candidats data.gouv + INSEE. Renvoie aussi la liste des sources en échec."""
    errors, out = [], []
    try:
        out += datagouv_search(queries)
    except Exception as e:  # noqa: BLE001
        errors.append(f"data.gouv.fr : {e}")
    try:
        out += preselect(melodi_index(), keywords + queries, 10)
    except Exception as e:  # noqa: BLE001
        errors.append(f"INSEE Melodi : {e}")
    return out, errors


# ════════════════════════════════════════════════════════════════════════════════
# FINANCEMENTS : AIDES-TERRITOIRES + MISSION TRANSITION ÉCOLOGIQUE
# ════════════════════════════════════════════════════════════════════════════════
AT_API = "https://aides-territoires.beta.gouv.fr/api/"
AT_BASE = "https://aides-territoires.beta.gouv.fr"
MTE_API = "https://mission-transition-ecologique.beta.gouv.fr/api/programs"
MTE_BASE = "https://mission-transition-ecologique.beta.gouv.fr"

# Type de porteur de projet → identifiant Aides-territoires
AT_AUDIENCES = {
    "Tous types de porteurs": None,
    "Commune": "commune",
    "Intercommunalité / Pays": "epci",
    "Département": "department",
    "Région": "region",
    "Établissement public / services de l'État": "public-org",
    "Entreprise": "private-sector",
    "Association": "association",
}


def aides_territoires_key() -> str:
    try:
        return st.secrets.get("AIDES_TERRITOIRES_API_KEY", "")
    except Exception:
        return ""


@st.cache_data(ttl=23 * 3600, show_spinner=False)
def _at_token(api_key: str) -> str:
    """Échange la clé API (permanente) contre un jeton valable 24 h."""
    r = requests.post(AT_API + "connexion/", headers={"X-AUTH-TOKEN": api_key,
                                                      "Content-Type": "application/json"},
                      data="{}", timeout=30)
    r.raise_for_status()
    tok = r.json().get("token")
    if not tok:
        raise RuntimeError("clé API refusée par Aides-territoires")
    return tok


def _at_get(path: str, params: dict) -> dict:
    tok = _at_token(aides_territoires_key())
    return _get_json(AT_API + path, params, {"Authorization": f"Bearer {tok}",
                                             "Accept": "application/json"}, timeout=60, tries=2)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def at_find_perimeter(query: str) -> dict | None:
    """« Seine-et-Marne » ou « 77 » → {"id": 71053, "name": ..., "scale": ...}."""
    query = (query or "").strip()
    if not query or not aides_territoires_key():
        return None
    if re.fullmatch(r"\d[\dAB]|\d{3}", query.upper()):   # numéro de département : 77, 2A, 974
        return {"code": query.upper(), "name": f"Département {query.upper()}", "scale": "Département"}
    d = _at_get("perimeters/", {"q": query, "itemsPerPage": 20})
    res = d.get("results", []) if isinstance(d, dict) else d
    prefer = ["Département", "Région", "Intercommunalité", "Commune"]
    res = sorted(res, key=lambda x: (norm(x.get("name", "")) != norm(query),   # nom exact d'abord
                                     not norm(x.get("name", "")).startswith(norm(query).rstrip()),
                                     prefer.index(x["scale"]) if x.get("scale") in prefer else 9))
    if not res:
        return None
    x = res[0]
    return {"id": str(x.get("id", "")).split("-")[0], "name": x.get("name"), "scale": x.get("scale")}


def _at_record(a: dict) -> dict:
    financeurs = [f.get("name", "") for f in a.get("financers_full") or [] if isinstance(f, dict)]
    lo, hi = a.get("subvention_rate_lower_bound"), a.get("subvention_rate_upper_bound")
    taux = f"{lo}–{hi} %" if lo and hi else (f"jusqu'à {hi} %" if hi else (f"{lo} %" if lo else ""))
    desc = strip_html(a.get("description") or "")
    return {
        "id": "at_" + str(a.get("id")),
        "source": "Aides-territoires",
        "titre": a.get("name", ""),
        "financeurs": financeurs,
        "nature": ", ".join(a.get("aid_types") or []),
        "territoire": a.get("perimeter") or "",
        "publics": a.get("targeted_audiences") or [],
        "date_limite": (a.get("submission_deadline") or "")[:10],
        "recurrence": a.get("recurrence") or "",
        "appel_a_projets": bool(a.get("is_call_for_project")),
        "taux": taux,
        "description": desc[:500],
        "url": AT_BASE + (a.get("url") or ""),
        "candidater": a.get("application_url") or a.get("origin_url") or "",
        "_idx": _idx(titre=(a.get("name", ""), 3.0), description=(desc, 1.0),
                     categories=(" ; ".join(a.get("categories") or []), 1.5)),
    }


def aides_territoires_search(keywords: list[str], audience: str | None = None,
                             perimeter: dict | None = None, per_kw: int = 30) -> list[dict]:
    """Aides ouvertes correspondant aux mots-clés (une requête par mot-clé, en parallèle)."""
    kws = split_keywords(keywords)
    # Mots-clés précis d'abord : les expressions de 2 mots, puis les mots seuls
    kws = sorted(kws, key=lambda k: -len(k.split()))[:8]

    def one(kw):
        params = {"keyword": kw, "itemsPerPage": per_kw}
        if audience:
            params["organization_type_slugs[]"] = audience
        if perimeter and perimeter.get("code"):
            params["perimeter_codes[]"] = perimeter["code"]
        elif perimeter and perimeter.get("id"):
            params["perimeter_id"] = perimeter["id"]
        try:
            return _at_get("aids/", params).get("results", [])
        except RuntimeError:
            return []

    _at_token(aides_territoires_key())  # erreur explicite si la clé est refusée
    seen, out = set(), []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for results in ex.map(one, kws):
            for a in results:
                if a.get("id") in seen or a.get("is_live") is False:
                    continue
                seen.add(a.get("id"))
                out.append(_at_record(a))
    return out


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def mte_index() -> list[dict]:
    """Aides aux entreprises recensées par Mission Transition Écologique (≈ 200 dispositifs)."""
    from datetime import date
    today = date.today()
    records = []
    for p in _get_json(MTE_API, timeout=60):
        fin = p.get("fin de validité") or ""
        try:
            j, m, a = (int(x) for x in fin.split("/"))
            if date(a, m, j) < today:
                continue
        except ValueError:
            pass
        desc = strip_html(" ".join(str(p.get(k) or "") for k in ("description", "description longue")))
        titre = p.get("titre", "")
        records.append({
            "id": "mte_" + str(p.get("id")),
            "source": "Mission Transition Écologique",
            "titre": titre,
            "financeurs": [p.get("opérateur de contact")] if p.get("opérateur de contact") else [],
            "nature": p.get("nature de l'aide") or "",
            "territoire": "",
            "publics": ["Entreprise"],
            "date_limite": "" if fin.endswith("2050") else fin,
            "recurrence": "",
            "appel_a_projets": False,
            "taux": "",
            "description": ((p.get("promesse") or "") + " — " + desc)[:500],
            "url": f"{MTE_BASE}/aides-entreprise/{p.get('id')}",
            "candidater": p.get("url") or "",
            "_idx": _idx(titre=(titre, 3.0), promesse=(p.get("promesse") or "", 2.0),
                         description=(desc, 1.0),
                         objectifs=(" ".join(str(o) for o in p.get("objectifs") or []), 1.0)),
        })
    return records


def funding_candidates(keywords: list[str], audience: str | None, perimeter: dict | None,
                       include_mte: bool) -> tuple[list[dict], list[str]]:
    """Candidats Aides-territoires + Mission Transition Écologique. Renvoie aussi les erreurs."""
    errors, out = [], []
    if aides_territoires_key():
        try:
            out += preselect(aides_territoires_search(keywords, audience, perimeter),
                             keywords, 30, min_score=0.5)
        except Exception as e:  # noqa: BLE001
            errors.append(f"Aides-territoires : {e}")
    else:
        errors.append("Aides-territoires : clé API absente (AIDES_TERRITOIRES_API_KEY dans les secrets)")
    if include_mte:
        try:
            out += preselect(mte_index(), keywords, 15)
        except Exception as e:  # noqa: BLE001
            errors.append(f"Mission Transition Écologique : {e}")
    return out, errors


# ════════════════════════════════════════════════════════════════════════════════
# BIBLIOGRAPHIE SCIENTIFIQUE : HAL, OPENALEX, LIBRAIRIE ADEME
# ════════════════════════════════════════════════════════════════════════════════
HAL_API = "https://api.archives-ouvertes.fr/search/"
OPENALEX_API = "https://api.openalex.org/works"
ADEME_LIB = "https://librairie.ademe.fr/recherche"

# Structures publiques mises en avant quand elles apparaissent dans HAL
PUBLIC_BODIES = ["CEREMA", "ADEME", "CNRS", "IFSTTAR", "UNIV-EIFFEL", "INRAE", "IRD", "INRIA",
                 "CIRAD", "BRGM", "IGN", "INED", "INSERM", "CEA", "IFPEN", "SANTE-PUBLIQUE-FRANCE"]
HAL_TYPES = {"ART": "Article", "COMM": "Communication", "OUV": "Ouvrage", "COUV": "Chapitre",
             "THESE": "Thèse", "REPORT": "Rapport", "HDR": "HDR", "MEM": "Mémoire",
             "UNDEFINED": "Prépublication", "OTHER": "Autre", "POSTER": "Poster"}


HAL_PUBLIC_FQ = ("collCode_s:(CEREMA OR UNIV-EIFFEL OR IFSTTAR) OR "
                 "structAcronym_s:(ADEME OR CEREMA OR IFSTTAR)")


def hal_search(queries: list[str], rows: int = 15, extra_fq: str | None = None) -> list[dict]:
    """Archives ouvertes HAL : CNRS, Cerema, ADEME, universités, organismes de recherche publics."""
    fl = ("docid,title_s,authFullName_s,producedDateY_i,docType_s,uri_s,abstract_s,"
          "structAcronym_s,collCode_s,journalTitle_s,doiId_s")

    def one(q):
        try:
            fq = ["docType_s:(ART OR COMM OR OUV OR COUV OR THESE OR REPORT OR UNDEFINED OR HDR)"]
            if extra_fq:
                fq.append(extra_fq)
            d = _get_json(HAL_API, {"q": q, "rows": rows, "wt": "json", "fl": fl, "fq": fq},
                          timeout=30, tries=2)
            return d.get("response", {}).get("docs", [])
        except RuntimeError:
            return []

    seen, out = set(), []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for docs in ex.map(one, queries[:6]):
            for x in docs:
                if x.get("docid") in seen:
                    continue
                seen.add(x.get("docid"))
                tags = set(x.get("structAcronym_s") or []) | set(x.get("collCode_s") or [])
                structures = [s for s in PUBLIC_BODIES if s in tags]
                titre = (x.get("title_s") or [""])[0]
                resume = strip_html((x.get("abstract_s") or [""])[0])
                auteurs = x.get("authFullName_s") or []
                out.append({
                    "id": "hal_" + str(x.get("docid")),
                    "source": "HAL",
                    "titre": titre,
                    "auteurs": ", ".join(auteurs[:3]) + (" et al." if len(auteurs) > 3 else ""),
                    "annee": x.get("producedDateY_i") or "",
                    "type": HAL_TYPES.get(x.get("docType_s"), x.get("docType_s") or ""),
                    "revue": x.get("journalTitle_s") or "",
                    "structures": structures,
                    "resume": resume[:900],
                    "url": x.get("uri_s") or "",
                    "_idx": _idx(titre=(titre, 3.0), resume=(resume, 1.0)),
                })
    return out


def _openalex_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = [(i, w) for w, idxs in inv.items() for i in idxs]
    return " ".join(w for _, w in sorted(pos))


def openalex_search(queries: list[str], per_query: int = 10) -> list[dict]:
    """Littérature scientifique internationale (OpenAlex, base ouverte et gratuite)."""
    def one(q):
        try:
            d = _get_json(OPENALEX_API, {
                "search": q, "per-page": per_query,
                "filter": "type:article|review|book-chapter|report|preprint",
                "select": "id,title,publication_year,authorships,abstract_inverted_index,doi,"
                          "cited_by_count,primary_location,open_access,type",
            }, timeout=30, tries=2)
            return d.get("results", [])
        except RuntimeError:
            return []

    seen, out = set(), []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for works in ex.map(one, queries[:5]):
            for w in works:
                if w.get("id") in seen or not w.get("title"):
                    continue
                seen.add(w.get("id"))
                auteurs = [a.get("author", {}).get("display_name", "") for a in w.get("authorships") or []]
                insts = {i.get("display_name", "") for a in w.get("authorships") or []
                         for i in a.get("institutions") or []}
                resume = _openalex_abstract(w.get("abstract_inverted_index"))
                src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
                url = (w.get("open_access") or {}).get("oa_url") or w.get("doi") or w.get("id")
                out.append({
                    "id": "oa_" + w["id"].rsplit("/", 1)[-1],
                    "source": "OpenAlex",
                    "titre": w["title"],
                    "auteurs": ", ".join(auteurs[:3]) + (" et al." if len(auteurs) > 3 else ""),
                    "annee": w.get("publication_year") or "",
                    "type": w.get("type") or "",
                    "revue": src,
                    "structures": sorted(i for i in insts if any(
                        k in i.upper() for k in ("CNRS", "CEREMA", "ADEME", "GUSTAVE EIFFEL", "INRAE")))[:3],
                    "citations": w.get("cited_by_count") or 0,
                    "resume": resume[:900],
                    "url": url,
                    "_idx": _idx(titre=(w["title"], 3.0), resume=(resume, 1.0)),
                })
    return out


def ademe_library_search(queries: list[str], per_query: int = 8) -> list[dict]:
    """Études, guides et rapports de la librairie ADEME (page de résultats du site)."""
    art_re = re.compile(r'<article class="product-miniature.*?</article>', re.S)

    def one(q):
        try:
            r = requests.get(ADEME_LIB, params={"controller": "search", "s": q}, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception:  # noqa: BLE001
            return ""

    seen, out = set(), []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for page in ex.map(one, queries[:4]):
            for art in art_re.findall(page)[:per_query]:
                m = re.search(r'<h3 class="fr-card__title">\s*<a href="([^"]+)">(.*?)</a>', art, re.S)
                if not m:
                    continue
                url = html.unescape(m.group(1)).split("#")[0]
                if url in seen:
                    continue
                seen.add(url)
                titre = strip_html(m.group(2))
                tags = [strip_html(t) for t in re.findall(r'<p class="fr-tag">(.*?)</p>', art, re.S)]
                details = [strip_html(t) for t in re.findall(r'<p class="fr-card__detail[^"]*">(.*?)</p>', art, re.S)]
                out.append({
                    "id": "ademe_" + str(abs(hash(url)) % 10**9),
                    "source": "Librairie ADEME",
                    "titre": titre,
                    "auteurs": "ADEME",
                    "annee": "",
                    "type": next((d for d in details if d and "Format" not in d), "Publication"),
                    "revue": "",
                    "structures": ["ADEME"],
                    "resume": " ; ".join(tags),
                    "url": url,
                    "_idx": _idx(titre=(titre, 3.0), themes=(" ".join(tags), 1.0)),
                })
    return out


def biblio_candidates(queries_fr: list[str], queries_en: list[str],
                      keywords: list[str]) -> tuple[list[dict], list[str]]:
    """Publications candidates des trois sources, présélectionnées par mots-clés."""
    errors, out = [], []
    jobs = {
        "HAL": lambda: preselect(hal_search(queries_fr), keywords + queries_fr, 20, min_score=0.5),
        "HAL (Cerema, ADEME, Univ. Gustave Eiffel)": lambda: preselect(
            hal_search(queries_fr, rows=8, extra_fq=HAL_PUBLIC_FQ), keywords + queries_fr, 10, min_score=0.5),
        "OpenAlex": lambda: preselect(openalex_search(queries_en), queries_en + keywords, 15, min_score=0.5),
        "Librairie ADEME": lambda: preselect(ademe_library_search(queries_fr), keywords + queries_fr, 10,
                                             min_score=0.5),
    }
    seen = set()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {name: ex.submit(fn) for name, fn in jobs.items()}
        for name, fut in futures.items():
            try:
                for r in fut.result():
                    if r["id"] not in seen:
                        seen.add(r["id"])
                        out.append(r)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name} : {e}")
    return out, errors
