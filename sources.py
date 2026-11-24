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
        score += best
    return score


def preselect(records: list[dict], keywords: list[str], n: int, min_score: float = 1.0,
              bonus: dict | None = None) -> list[dict]:
    """Garde les n fiches au meilleur score. `bonus` : {titre: points ajoutés}."""
    bonus = bonus or {}
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
        for d in ex.map(one, keywords[:6]):
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
def datagouv_search(queries: list[str], per_query: int = 8) -> list[dict]:
    """Recherche de jeux de données et d'API sur data.gouv.fr (API publique, sans clé)."""
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
