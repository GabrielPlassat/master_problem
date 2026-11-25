"""
Formulateur de Sous-Problème Stratégique – Transition Écologique
Outil Streamlit + Claude API
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import io
import re
import copy
from datetime import datetime

import sources

# ─── CONFIG PAGE ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Formulateur Stratégique – Transition Écologique",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CLÉ API — chargée depuis st.secrets ────────────────────────────────────────
def get_api_key() -> str:
    """Charge la clé API depuis st.secrets (secrets.toml ou Streamlit Cloud)."""
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        return ""

API_KEY = get_api_key()

# ─── STYLES ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.phase-header {
    background: linear-gradient(135deg, #1a7a4a, #2d9d6a);
    padding: 20px 28px;
    border-radius: 12px;
    color: white;
    margin-bottom: 24px;
}
.phase-header h2 { color: white; margin: 0 0 6px 0; }
.phase-header p  { color: #d4f5e9; margin: 0; }
.hmw-box {
    background: linear-gradient(135deg, #0f4c75, #1b6ca8);
    padding: 28px;
    border-radius: 14px;
    color: white;
    text-align: center;
    margin: 20px 0;
}
.hmw-box h3 { color: white; font-size: 1.4rem; margin: 0; line-height: 1.5; }
.score-box {
    border: 2px solid #e0e0e0;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES ─────────────────────────────────────────────────────────────────
PHASES = [
    ("1", "Ancrage",                  "Comprendre et clarifier le problème général"),
    ("2", "Miroir des Impossibles",   "Déstabiliser les certitudes de l'expert"),
    ("3", "Scout Technologique",      "Explorer les solutions venues d'ailleurs"),
    ("4", "Décomposition",            "Identifier les sous-problèmes candidats"),
    ("5", "Ressources & Contraintes", "Décrire précisément vos moyens"),
    ("6", "Test de Cohérence",        "Évaluer la faisabilité du sous-problème"),
    ("7", "Formulation Finale",       "Formuler, exporter et agir"),
    ("8", "Communs & Ressources",      "Ce qui existe déjà sur le wiki de la Fabrique des Mobilités"),
    ("9", "Solutions & Acteurs",       "Solutions déjà déployées, recensées par France Mobilités"),
    ("10", "Données Ouvertes",         "Données pour mesurer et piloter (data.gouv.fr, INSEE)"),
    ("11", "Financements",             "Aides publiques ouvertes (Aides-territoires, Mission Transition Écologique)"),
    ("12", "Synthèse & Export",        "Votre fiche enrichie, prête à partager"),
]

CYNEFIN_INFO = {
    "Clair":      ("🟢", "Relations cause-effet connues. Appliquer les meilleures pratiques."),
    "Compliqué":  ("🟡", "Plusieurs bonnes réponses. Requiert expertise et analyse."),
    "Complexe":   ("🟠", "Imprévisible. Expérimenter, observer, adapter."),
    "Pernicieux": ("🔴", "Pas de solution définitive. Problème social profond (Wicked Problem)."),
}

# ─── SESSION STATE ───────────────────────────────────────────────────────────────
DEFAULTS = {
    "phase": 0,
    "max_phase": 0,             # phase la plus avancée atteinte (pour la navigation)
    "doc_text": "",
    "sofia_data": None,
    "problem_input": "",
    "reformulation": "",
    "cynefin": "",
    "ambiguites": [],
    "manques": [],
    # Phase 2 — Miroir des Impossibles
    "miroir_cas": [],           # liste des cas générés
    "miroir_reactions": {},     # réactions de l'expert par cas
    "miroir_lecon": "",         # leçon tirée par l'expert
    # Phase 3 — Scout Technologique
    "scout_techs": [],          # technologies candidates générées
    "scout_selections": [],     # technologies retenues par l'expert
    "scout_ouvertures": "",     # reformulation après le scout
    # Phase 4 — Décomposition
    "sub_problems": [],
    "selected_sub_problems_list": [],
    "selected_sub_problem": "",
    # Phases suivantes
    "resources": {},
    "constraints": {},
    "coherence_score": None,
    "coherence_details": {},
    "hmw": "",
    "final_data": {},
    # Phases 8 à 11 — explorer ce qui existe déjà
    "mots_cles": [],            # mots-clés du problème (partagés par les phases 8 à 11)
    "requetes_donnees": [],     # requêtes de recherche de données ouvertes
    "wiki_results": {},         # {type: [fiches classées par Claude]}
    "wiki_synthese": "",
    "fm_results": [],           # solutions France Mobilités classées
    "fm_synthese": "",
    "data_results": [],         # jeux de données classés
    "data_synthese": "",
    "fin_results": [],          # aides financières classées par Claude
    "fin_synthese": "",
    "fin_porteur": "Tous types de porteurs",
    "fin_territoire": "",
    "retenus": {},              # {id: fiche} — ressources retenues par l'expert
    "feuille_route": {},        # synthèse finale générée en phase 11
    "_synth_data": None,
    "_sel_sig": None,
    "_direct_entry": False,     # problème saisi directement en phase 7
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = copy.deepcopy(v)

# Clés techniques à conserver lors d'un Reset / d'une restauration
_KEEP_KEYS = {"restore_file", "_restored_sig"}

# ─── HELPERS ────────────────────────────────────────────────────────────────────

def parse_sofia_html(html_content: str) -> dict:
    """
    Parse un rapport HTML exporté par SofIA (sofia-transition-ecologique.fr).
    Retourne un dict structuré avec questions, reformulations, réponses et sources ADEME.
    """
    from html.parser import HTMLParser
    import re

    # Utilise BeautifulSoup si disponible, sinon regex fallback
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Date de la conversation
        h1 = soup.find("h1")
        date_conv = h1.get_text(strip=True) if h1 else ""

        exchanges = []

        # Questions
        questions = soup.find_all("div", class_="question")
        reformulations = soup.find_all("div", class_="reformulation")
        responses = soup.find_all("div", class_="response")
        sources_blocks = soup.find_all("div", class_="sources")

        for i, (q, resp) in enumerate(zip(questions, responses)):
            # Question brute
            q_text = q.get_text(separator=" ", strip=True)
            q_text = re.sub(r"^\d+\.\s*Question\s*:", "", q_text).strip()

            # Reformulation SofIA
            ref_text = ""
            if i < len(reformulations):
                ref_text = reformulations[i].get_text(separator=" ", strip=True)
                ref_text = re.sub(r"Reformulation de la question\s*:", "", ref_text).strip()

            # Réponse SofIA (texte enrichi)
            # On garde le texte principal, on supprime les balises h2 "Sofia:"
            for tag in resp.find_all("h2"):
                tag.decompose()
            resp_text = resp.get_text(separator="\n", strip=True)
            # Nettoyage des artefacts HTML
            resp_text = re.sub(r"\n{3,}", "\n\n", resp_text)

            # Sources ADEME associées
            sources = []
            if i < len(sources_blocks):
                cards = sources_blocks[i].find_all("div", class_="source-card")
                for card in cards:
                    card_id = card.get("id", "")
                    title_tag = card.find("h2", class_="card-title")
                    title = title_tag.get_text(strip=True) if title_tag else ""
                    # Lien PDF
                    link_tag = card.find("a", href=True)
                    link = link_tag["href"] if link_tag else ""
                    # Texte extrait
                    text_tag = card.find("p", class_="card-text")
                    excerpt = text_tag.get_text(separator=" ", strip=True) if text_tag else ""
                    # Score de pertinence
                    score_tag = card.find("p", class_="card-similarity")
                    score_str = score_tag.get_text(strip=True) if score_tag else ""
                    score_val = re.search(r"([\d.]+)\s*%", score_str)
                    score_pct = float(score_val.group(1)) if score_val else 0.0

                    sources.append({
                        "id": card_id,
                        "titre": title,
                        "lien": link,
                        "extrait": excerpt[:400],
                        "score_pertinence": score_pct,
                    })
                # Tri par score décroissant
                sources.sort(key=lambda x: x["score_pertinence"], reverse=True)

            exchanges.append({
                "question": q_text,
                "reformulation_sofia": ref_text,
                "reponse_sofia": resp_text[:3000],  # Cap pour éviter token overflow
                "nb_sources": len(sources),
                "sources_top5": sources[:5],
            })

        return {
            "is_sofia": True,
            "date": date_conv,
            "nb_echanges": len(exchanges),
            "exchanges": exchanges,
        }

    except ImportError:
        # Fallback regex si BeautifulSoup absent
        import re
        questions = re.findall(r'class="question"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        responses = re.findall(r'class="response"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        clean = lambda s: re.sub(r"<[^>]+>", " ", s).strip()
        exchanges = [
            {"question": clean(q), "reponse_sofia": clean(r)[:2000], "sources_top5": []}
            for q, r in zip(questions, responses)
        ]
        return {"is_sofia": True, "date": "", "nb_echanges": len(exchanges), "exchanges": exchanges}


def sofia_to_context(sofia_data: dict) -> str:
    """Convertit les données SofIA en bloc de contexte structuré pour Claude."""
    lines = [
        f"=== RAPPORT SOFIA — Transition Écologique ===",
        f"Date : {sofia_data.get('date', '')}",
        f"Nombre d'échanges : {sofia_data.get('nb_echanges', 0)}",
        "",
    ]
    for i, ex in enumerate(sofia_data.get("exchanges", []), 1):
        lines.append(f"── Échange {i} ──")
        lines.append(f"QUESTION : {ex.get('question', '')}")
        if ex.get("reformulation_sofia"):
            lines.append(f"REFORMULATION SOFIA : {ex.get('reformulation_sofia', '')}")
        lines.append(f"RÉPONSE SOFIA (synthèse ADEME) :\n{ex.get('reponse_sofia', '')}")
        top_sources = ex.get("sources_top5", [])
        if top_sources:
            lines.append(f"\nSOURCES ADEME LES PLUS PERTINENTES ({len(top_sources)}) :")
            for s in top_sources:
                lines.append(
                    f"  • [{s.get('score_pertinence', 0):.1f}%] {s.get('titre', '')} — {s.get('extrait', '')[:200]}"
                )
        lines.append("")
    return "\n".join(lines)


def extract_text(uploaded_file) -> str:
    """Extrait le texte d'un fichier PDF, DOCX, TXT ou HTML SofIA."""
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
    raw_bytes = uploaded_file.read()
    try:
        if ext == "txt":
            return raw_bytes.decode("utf-8", errors="ignore")
        elif ext == "pdf":
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        elif ext in ("docx", "doc"):
            from docx import Document
            doc = Document(io.BytesIO(raw_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        elif ext in ("html", "htm"):
            html_str = raw_bytes.decode("utf-8", errors="ignore")
            # Détecte si c'est un rapport SofIA
            if "sofia" in html_str.lower()[:2000] or "class=\"question\"" in html_str or "card-similarity" in html_str:
                sofia_data = parse_sofia_html(html_str)
                # Stocke aussi les données structurées pour affichage
                st.session_state["sofia_data"] = sofia_data
                return sofia_to_context(sofia_data)
            else:
                # HTML générique : strip balises
                import re
                return re.sub(r"<[^>]+>", " ", html_str)
    except Exception as e:
        st.error(f"Erreur lecture {uploaded_file.name} : {e}")
    return ""


def claude(prompt: str, system: str = None, max_tokens: int = 2000) -> str | None:
    """Appel Claude API via requests (sans SDK anthropic)."""
    if not API_KEY:
        st.error("⚠️ Clé API manquante. Ajoutez ANTHROPIC_API_KEY dans .streamlit/secrets.toml")
        return None
    sys = system or (
        "Tu es un consultant senior spécialisé en transition écologique et formulation "
        "de problèmes stratégiques. Tu réponds en français, avec précision et pédagogie."
    )
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": max_tokens,
                "system": sys,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        data = response.json()
        if "content" not in data:
            st.error(f"Erreur API : {data.get('error', {}).get('message', str(data))}")
            return None
        return data["content"][0]["text"]
    except Exception as e:
        st.error(f"Erreur API : {e}")
        return None


def parse_json(raw: str) -> dict | list | None:
    """Parse JSON en nettoyant les éventuels blocs markdown."""
    if not raw:
        return None
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(clean)
    except Exception as e:
        st.error(f"Erreur de parsing JSON : {e}\n\nRéponse brute : {raw[:300]}")
        return None


def score_emoji(s: int, max_s: int = 100) -> str:
    pct = s / max_s * 100
    return "🟢" if pct >= 70 else "🟡" if pct >= 40 else "🔴"


def set_phase(n: int):
    """Change de phase (utilisable en callback on_click). Mémorise la phase max atteinte."""
    n = max(0, min(int(n), len(PHASES) - 1))
    st.session_state.phase = n
    st.session_state.max_phase = max(st.session_state.get("max_phase", 0), n)


def next_phase():
    set_phase(st.session_state.phase + 1)


def go_phase(n: int):
    set_phase(n)
    st.rerun()


# ─── SAUVEGARDE / RESTAURATION ──────────────────────────────────────────────────
SAVE_APP_ID = "formulateur_strategique"


def build_save() -> str:
    """Sérialise toute la progression (toutes les phases) en JSON."""
    state = {k: st.session_state.get(k, v) for k, v in DEFAULTS.items()}
    payload = {
        "app": SAVE_APP_ID,
        "version": 2,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "phase_label": PHASES[st.session_state.phase][1],
        "state": state,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def save_filename() -> str:
    num = PHASES[st.session_state.phase][0]
    return f"sauvegarde_phase{num}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"


def export_to_state(payload: dict) -> dict | None:
    """Convertit un fichier « Exporter en JSON » de l'étape 7 en état de l'outil.

    Ce fichier contient le problème formulé mais pas tout le travail des phases 1 à 6 :
    on reprend donc à l'étape 7, d'où l'on peut lancer la recherche de ressources.
    """
    if not isinstance(payload, dict) or not (
            payload.get("formulation_hmw") or payload.get("formulation_complete")):
        return None
    coh = payload.get("coherence") or {}
    details = dict(coh.get("detail") or {})
    if coh.get("verdict"):
        details["verdict"] = coh["verdict"]
    return {
        "phase": 6,
        "max_phase": 6,
        "reformulation": payload.get("probleme_general") or "",
        "selected_sub_problem": payload.get("sous_probleme_retenu") or "",
        "hmw": payload.get("formulation_hmw") or payload.get("formulation_complete") or "",
        "final_data": {
            "hmw": payload.get("formulation_hmw") or "",
            "formulation_complete": payload.get("formulation_complete") or "",
            "indicateurs_succes": payload.get("indicateurs_succes") or [],
            "prochaines_etapes": payload.get("prochaines_etapes") or [],
            "risques_principaux": payload.get("risques") or payload.get("risques_principaux") or [],
            "questions_restantes": payload.get("questions_restantes") or [],
        },
        "coherence_score": coh.get("score"),
        "coherence_details": details,
        "resources": payload.get("ressources") or {},
        "constraints": payload.get("contraintes") or {},
    }


def load_save(raw: bytes) -> str | None:
    """Restaure une sauvegarde (ou un export JSON de l'étape 7). Renvoie une erreur, ou None si OK."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return "Fichier illisible : ce n'est pas un JSON valide."
    if isinstance(payload, dict) and payload.get("app") == SAVE_APP_ID \
            and isinstance(payload.get("state"), dict):
        state = payload["state"]
    else:
        state = export_to_state(payload)
        if state is None:
            return ("Ce fichier n'est ni une sauvegarde de l'outil, ni un export de l'étape 7. "
                    "Utilisez le bouton « 💾 Sauvegarder ma progression » pour en créer une.")
    # On efface l'état courant (y compris les champs de saisie mémorisés)
    for k in list(st.session_state.keys()):
        if k not in _KEEP_KEYS:
            del st.session_state[k]
    for k, v in DEFAULTS.items():
        st.session_state[k] = copy.deepcopy(state.get(k, v))
    try:
        phase = max(0, min(int(st.session_state.phase), len(PHASES) - 1))
    except (TypeError, ValueError):
        phase = 0
    st.session_state.phase = phase
    try:
        st.session_state.max_phase = max(phase, min(int(st.session_state.max_phase), len(PHASES) - 1))
    except (TypeError, ValueError):
        st.session_state.max_phase = phase
    return None


# ─── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌿 Formulateur Stratégique")
    st.caption("Transition Écologique — Outil de cadrage")

    # Indicateur de statut API (discret)
    if API_KEY:
        st.caption("🟢 API connectée")
    else:
        st.error("🔴 Clé API manquante\n\nAjoutez `ANTHROPIC_API_KEY` dans `.streamlit/secrets.toml`")

    st.divider()
    st.markdown("### 📍 Progression")
    st.caption("Cliquez sur une phase déjà atteinte pour y revenir.")
    for i, (num, name, _) in enumerate(PHASES):
        if i == st.session_state.phase:
            st.markdown(f"▶️ **Phase {num} – {name}** ← ici")
        elif i <= st.session_state.max_phase:
            st.button(f"✅ Phase {num} – {name}", key=f"nav_{i}",
                      on_click=set_phase, args=(i,), use_container_width=True)
        else:
            st.markdown(f"⬜ Phase {num} – {name}")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.button("◀ Retour", disabled=st.session_state.phase == 0, use_container_width=True,
                  on_click=set_phase, args=(st.session_state.phase - 1,), key="back_sidebar")
    with col2:
        if st.button("🔄 Reset", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k not in _KEEP_KEYS:
                    del st.session_state[k]
            for k, v in DEFAULTS.items():
                st.session_state[k] = copy.deepcopy(v)
            st.rerun()

    st.divider()
    st.markdown("### 💾 Sauvegarder")
    st.caption(
        "Téléchargez un fichier qui contient tout votre travail, pour le reprendre plus tard "
        "sans tout refaire."
    )
    # Rempli en fin de script, pour que la sauvegarde contienne les dernières saisies
    sidebar_save_slot = st.empty()

    st.markdown("### 📂 Reprendre un travail")
    st.caption(
        "**Déposez ici votre fichier de sauvegarde** (.json) : l'outil vous ramène directement "
        "à l'étape où vous vous étiez arrêté. Le fichier « Exporter en JSON » de l'étape 7 "
        "fonctionne aussi : vous reprenez alors au problème formulé."
    )
    restore = st.file_uploader("Fichier de sauvegarde à reprendre", type=["json"], key="restore_file",
                               label_visibility="collapsed")
    if restore is not None:
        sig = f"{restore.name}-{restore.size}"
        if st.session_state.get("_restored_sig") != sig:
            err = load_save(restore.getvalue())
            if err:
                st.error(err)
            else:
                st.session_state["_restored_sig"] = sig
                st.rerun()
        else:
            st.success(f"Sauvegarde chargée : {restore.name}")

    st.divider()
    st.caption("Basé sur : Cynefin (Snowden), Problem Statement Canvas, JTBD, Double Diamant, HMW (IDEO), Frame Innovation (Dorst)")


# ─── PHASE HEADER HELPER ────────────────────────────────────────────────────────
def phase_header(num, name, desc):
    st.markdown(f"""
<div class="phase-header">
  <h2>Phase {num} — {name}</h2>
  <p>{desc}</p>
</div>
""", unsafe_allow_html=True)


# ─── PHASES 8-11 : HELPERS ──────────────────────────────────────────────────────
def problem_brief() -> str:
    """Le problème final, tel que formulé en phase 7 (ou à défaut le sous-problème)."""
    fd = st.session_state.final_data or {}
    parts = []
    if st.session_state.hmw:
        parts.append(f"Formulation « Comment pourrions-nous » : {st.session_state.hmw}")
    if fd.get("formulation_complete"):
        parts.append(f"Brief : {fd['formulation_complete']}")
    if st.session_state.selected_sub_problem:
        parts.append(f"Sous-problème : {st.session_state.selected_sub_problem}")
    if st.session_state.reformulation:
        parts.append(f"Problème général : {st.session_state.reformulation}")
    return "\n".join(parts)


def reset_exploration():
    """Nouveau problème : les mots-clés et résultats des phases 8 à 11 ne sont plus valables."""
    for k in ("mots_cles", "requetes_donnees", "wiki_results", "wiki_synthese", "fm_results",
              "fm_synthese", "data_results", "data_synthese", "fin_results", "fin_synthese",
              "feuille_route"):
        st.session_state[k] = copy.deepcopy(DEFAULTS[k])


def set_canonical(url: str | None):
    """Ajoute (ou retire) la balise <link rel="canonical"> dans l'en-tête de la page.

    Consigne de France Mobilités : tout site tiers qui expose leurs données doit indiquer,
    par une balise canonical, l'URL de la page d'origine sur francemobilites.fr.
    """
    js_url = json.dumps(url or "")
    script = f"""<script>
    (function() {{
      try {{
        const doc = (window.parent && window.parent.document) || document;
        let link = doc.head.querySelector('link[rel="canonical"][data-source="francemobilites"]');
        const url = {js_url};
        if (!url) {{ if (link) link.remove(); return; }}
        if (!link) {{
          link = doc.createElement('link');
          link.setAttribute('rel', 'canonical');
          link.setAttribute('data-source', 'francemobilites');
          doc.head.appendChild(link);
        }}
        link.setAttribute('href', url);
      }} catch (e) {{}}
    }})();
    </script>"""
    try:
        st.html(script, unsafe_allow_javascript=True)
    except TypeError:  # anciennes versions de Streamlit
        components.html(script, height=0)


def require_problem() -> bool:
    if not st.session_state.hmw and not st.session_state.selected_sub_problem:
        st.warning("⚠️ Formulez d'abord votre problème (phase 7), ou rechargez une sauvegarde.")
        return False
    st.info(f"**Problème** : {st.session_state.hmw or st.session_state.selected_sub_problem}")
    return True


def ensure_keywords(force: bool = False) -> bool:
    """Demande à Claude les mots-clés et requêtes de recherche, une seule fois."""
    if st.session_state.mots_cles and not force:
        return True
    prompt = f"""{problem_brief()}

Pour rechercher ce qui existe déjà sur ce problème (communs, projets, solutions, acteurs, données ouvertes),
fournis en JSON valide (aucun markdown) :
- "mots_cles" : 10 à 15 mots-clés SIMPLES EN FRANÇAIS, un seul mot de préférence (deux au maximum, jamais de phrase), tels qu'on les taperait dans un moteur de recherche. Du plus spécifique au plus général, avec les synonymes usuels du secteur. Exemple : ["covoiturage", "autopartage", "rural", "périurbain", "domicile-travail", "navette", "autostop"]. Pas de mots vides, pas de termes trop génériques comme "mobilité" seul.
- "requetes_donnees" : 4 à 6 requêtes de 1 ou 2 mots pour chercher des jeux de données ouverts utiles pour mesurer ce problème et ses indicateurs. Exemple : ["covoiturage", "aires covoiturage", "domicile-travail", "transport public"]."""
    with st.spinner("Extraction des mots-clés du problème…"):
        data = parse_json(claude(prompt, max_tokens=800))
    if not data:
        return False
    st.session_state.mots_cles = [str(k) for k in data.get("mots_cles", []) if str(k).strip()]
    st.session_state.requetes_donnees = [str(k) for k in data.get("requetes_donnees", []) if str(k).strip()]
    return bool(st.session_state.mots_cles)


def _split_list(txt: str) -> list[str]:
    """Liste saisie par l'expert : virgules, points-virgules ou retours à la ligne."""
    out = []
    for k in re.split(r"[,;\n]+", txt or ""):
        k = k.strip()
        if k and k.lower() not in (o.lower() for o in out):
            out.append(k)
    return out


def keywords_editor(show_queries: bool = False):
    """Affiche les mots-clés, modifiables par l'expert."""
    with st.expander("🔑 Mots-clés utilisés pour la recherche (modifiables)",
                     expanded=bool(st.session_state.mots_cles)):
        st.caption("Des **mots simples séparés par des virgules** donnent les meilleurs résultats "
                   "(ex : *covoiturage, rural, autopartage*). Une expression longue est découpée "
                   "automatiquement en mots. Laissez vide pour que Claude les propose.")
        txt = st.text_area(
            "Mots-clés (séparés par des virgules)",
            value=", ".join(st.session_state.mots_cles), height=80,
        )
        st.session_state.mots_cles = _split_list(txt)
        if show_queries:
            txt2 = st.text_area(
                "Recherches de données ouvertes (1 ou 2 mots chacune, séparées par des virgules)",
                value=", ".join(st.session_state.requetes_donnees), height=60,
            )
            st.session_state.requetes_donnees = _split_list(txt2)
        if st.button("🔄 Régénérer les mots-clés avec Claude", disabled=not API_KEY):
            if ensure_keywords(force=True):
                st.rerun()


def rank_with_claude(candidates: list[dict], what: str, summary_fn, max_items: str,
                     extra: str = "") -> tuple[list[dict], str]:
    """Claude choisit et explique les candidats les plus pertinents.

    Les candidats sont référencés par un identifiant court : Claude ne peut donc
    citer que des fiches réellement trouvées (pas de lien inventé).
    """
    if not candidates:
        return [], ""
    by_id = {f"c{i}": c for i, c in enumerate(candidates, 1)}
    listing = "\n".join(f"[{cid}] {summary_fn(c)}" for cid, c in by_id.items())
    prompt = f"""{problem_brief()}

Voici des {what} présélectionnés automatiquement par mots-clés (certains peuvent être hors sujet) :
{listing}

Sélectionne {max_items} les plus utiles pour l'expert qui doit traiter CE problème. Écarte ceux qui sont hors sujet.{extra}
Réponds UNIQUEMENT en JSON valide (aucun markdown) :
{{"selection": [{{"id": "c3", "pertinence": "forte" | "moyenne", "pourquoi": "1 phrase : en quoi c'est lié au problème", "comment_mobiliser": "1 phrase : ce que l'expert peut en faire concrètement (réutiliser, contacter, s'inspirer, contribuer...)"}}],
 "synthese": "2-3 phrases : ce qui existe déjà, et ce qui semble manquer (angle mort, opportunité)"}}"""
    with st.spinner(f"Claude analyse les {len(candidates)} {what} trouvés…"):
        data = parse_json(claude(prompt, max_tokens=3500))
    if not data:
        return [], ""
    out = []
    for item in data.get("selection", []):
        c = by_id.get(str(item.get("id", "")).strip())
        if c:
            out.append({**c, "pertinence": item.get("pertinence", ""),
                        "pourquoi": item.get("pourquoi", ""),
                        "comment_mobiliser": item.get("comment_mobiliser", "")})
    return out, data.get("synthese", "")


def toggle_retenu(item: dict):
    ret = st.session_state.retenus
    if item["_key"] in ret:
        del ret[item["_key"]]
    else:
        ret[item["_key"]] = {k: v for k, v in item.items() if not k.startswith("_")}


def show_item(item: dict, origin: str, details: list[str]):
    """Carte d'une ressource : titre cliquable, pertinence, explications, case « retenir »."""
    key = f"{origin}:{item.get('url') or item.get('titre')}"
    item["_key"] = key
    item["origine"] = origin
    badge = "🟢" if item.get("pertinence") == "forte" else "🟡"
    with st.container(border=True):
        c1, c2 = st.columns([5, 1])
        with c1:
            titre = item.get("titre", "")
            st.markdown(f"{badge} **[{titre}]({item['url']})**" if item.get("url") else f"{badge} **{titre}**")
            meta = " · ".join(d for d in details if d)
            if meta:
                st.caption(meta)
            if item.get("pourquoi"):
                st.markdown(f"🔗 {item['pourquoi']}")
            if item.get("comment_mobiliser"):
                st.markdown(f"👉 *{item['comment_mobiliser']}*")
        with c2:
            st.checkbox("Retenir", value=key in st.session_state.retenus,
                        key=f"keep_{key}", on_change=toggle_retenu, args=(item,))


def show_source_error(name: str, err: Exception):
    st.error(f"⚠️ {name} est momentanément inaccessible. Réessayez plus tard.\n\n`{err}`")


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 0 — ANCRAGE
# ════════════════════════════════════════════════════════════════════════════════
if st.session_state.phase == 0:
    phase_header("1", "Ancrage", "Décrire et clarifier votre problème général. Briser l'illusion de clarté.")

    st.markdown("""
> *"Tomber amoureux du problème, pas de la solution."* — Marty Cagan
>
> Beaucoup d'experts pensent avoir un problème clair. Ce qu'ils ont, c'est souvent **une intention**.
> Cette phase va révéler les zones d'ombre avant d'aller plus loin.
""")

    def _go_direct():
        st.session_state["_direct_entry"] = True
        set_phase(6)

    c_info, c_btn = st.columns([3, 1])
    with c_info:
        st.info("**Vous avez déjà un problème bien formulé ?** Passez directement à l'étape 7 pour le "
                "saisir et chercher les communs, solutions, acteurs et données ouvertes associés.")
    with c_btn:
        st.button("✍️ Saisir mon problème →", on_click=_go_direct, use_container_width=True)

    # ── Upload documents ──
    st.subheader("📎 Documents de contexte")

    col_tip1, col_tip2 = st.columns(2)
    with col_tip1:
        st.info(
            "**💡 Rapport SofIA recommandé**\n\n"
            "Consultez d'abord [SofIA](https://www.sofia-transition-ecologique.fr) "
            "(IA de l'ADEME) pour interroger la base documentaire sur votre thématique, "
            "puis exportez l'historique en HTML et uploadez-le ici.\n\n"
            "L'outil reconnaît automatiquement ce format et extrait questions, "
            "réponses et sources ADEME."
        )
    with col_tip2:
        st.markdown(
            "**Autres formats acceptés :**\n"
            "- 📄 PDF (rapports, études)\n"
            "- 📝 DOCX (cahiers des charges)\n"
            "- 🌐 HTML (rapport SofIA exporté)\n"
            "- 📋 TXT (notes, synthèses)\n"
        )

    files = st.file_uploader(
        "Glissez vos documents ici",
        accept_multiple_files=True,
        type=["pdf", "docx", "txt", "html", "htm"],
        label_visibility="collapsed"
    )
    if files:
        texts = []
        sofia_detected = False
        for f in files:
            t = extract_text(f)
            if t:
                texts.append(f"=== {f.name} ===\n{t}")
            if st.session_state.get("sofia_data"):
                sofia_detected = True

        st.session_state.doc_text = "\n\n".join(texts)
        nb_chars = len(st.session_state.doc_text)

        if sofia_detected and st.session_state.sofia_data:
            sd = st.session_state.sofia_data
            st.success(f"✅ Rapport SofIA détecté — {sd['nb_echanges']} échange(s) analysé(s)")
            st.markdown(f"**{sd.get('date', '')}**")

            for i, ex in enumerate(sd.get("exchanges", []), 1):
                with st.expander(f"💬 Échange {i} : {ex.get('question', '')[:80]}…"):
                    st.markdown(f"**Question :** {ex.get('question', '')}")
                    if ex.get("reformulation_sofia"):
                        st.markdown(f"**Reformulation SofIA :** *{ex.get('reformulation_sofia', '')}*")
                    st.markdown("**Réponse SofIA (extrait) :**")
                    st.markdown(ex.get("reponse_sofia", "")[:1500] + "…")

                    top_src = ex.get("sources_top5", [])
                    if top_src:
                        st.markdown(f"**📚 {ex.get('nb_sources', len(top_src))} sources ADEME — Top 5 :**")
                        for s in top_src:
                            score_color = "🟢" if s["score_pertinence"] > 10 else "🟡" if s["score_pertinence"] > 5 else "🔴"
                            lien_md = f"[↗]({s['lien']})" if s.get("lien") else ""
                            st.markdown(
                                f"  {score_color} **{s['score_pertinence']:.1f}%** — {s.get('titre', '')} {lien_md}"
                            )
        else:
            st.success(f"✅ {len(files)} document(s) chargé(s) — {nb_chars:,} caractères extraits")
            with st.expander("Aperçu du texte extrait"):
                st.text(st.session_state.doc_text[:3000] + ("…" if nb_chars > 3000 else ""))

    st.divider()

    # ── Saisie libre ──
    st.subheader("✍️ Décrivez votre problème général")
    st.caption("Exprimez-vous librement. Ne pensez pas encore à la solution ni aux ressources.")
    problem_input = st.text_area(
        "Problème général",
        value=st.session_state.problem_input,
        height=160,
        placeholder=(
            "Ex : Les émissions de GES liées à la logistique urbaine continuent d'augmenter "
            "malgré les réglementations. Les opérateurs peinent à adapter leurs flottes. "
            "Les collectivités manquent de données pour agir efficacement..."
        ),
        label_visibility="collapsed"
    )
    st.session_state.problem_input = problem_input

    can_analyze = bool(problem_input.strip()) and bool(API_KEY)

    if not API_KEY:
        st.warning("⚠️ Renseignez votre clé API Anthropic dans la barre latérale.")

    if st.button("🔍 Analyser mon problème", type="primary", disabled=not can_analyze):
        # Contexte : priorité au rapport SofIA (données ADEME structurées)
        context_block = ""
        if st.session_state.get("sofia_data"):
            sd = st.session_state.sofia_data
            sofia_lines = [
                "CONTEXTE ISSU DE SOFIA (base documentaire ADEME — source de référence) :",
                f"Date de consultation : {sd.get('date', '')}",
                "",
            ]
            for i, ex in enumerate(sd.get("exchanges", []), 1):
                sofia_lines.append(f"Q{i} posée par l'expert : {ex.get('question', '')}")
                sofia_lines.append(f"Synthèse ADEME : {ex.get('reponse_sofia', '')[:800]}")
                top5 = ex.get("sources_top5", [])
                if top5:
                    sofia_lines.append("Sources ADEME mobilisées : " +
                        " | ".join(f"{s['titre'][:50]} ({s['score_pertinence']:.0f}%)" for s in top5[:3]))
                sofia_lines.append("")
            context_block = "\n".join(sofia_lines)[:5000] + "\n\n"
        elif st.session_state.doc_text:
            context_block = f"DOCUMENTS FOURNIS :\n{st.session_state.doc_text[:4000]}\n\n"

        sofia_instruction = ""
        if st.session_state.get("sofia_data"):
            sofia_instruction = (
                "\nATTENTION : Le contexte provient de SofIA (IA de l'ADEME). "
                "Utilise les données chiffrées, objectifs réglementaires et retours d'expérience "
                "identifiés dans les échanges SofIA pour enrichir ton analyse et tes recommandations. "
                "Cite les données concrètes issues des sources ADEME pour justifier ta classification Cynefin."
            )

        prompt = f"""{context_block}L'expert décrit son problème général :
"{problem_input}"{sofia_instruction}

Réalise une analyse structurée. Réponds UNIQUEMENT en JSON valide (pas de markdown, pas de backticks) avec ces clés :
- "reformulation" : reformulation précise en 2-3 phrases, fidèle à l'expert mais sans ambiguïté. Si des données SofIA/ADEME sont disponibles, intègre les éléments factuels clés (objectifs, chiffres, contexte réglementaire).
- "cynefin" : objet avec "categorie" (Clair|Compliqué|Complexe|Pernicieux) et "justification" (1-2 phrases, appuyée sur les données disponibles)
- "ambiguites" : liste de 3-5 formulations ambiguës ou zones d'ombre dans l'énoncé
- "manques" : liste de 3-4 informations clés absentes qui empêchent de bien cerner le problème (ne pas signaler ce qui est déjà fourni par SofIA)
"""
        with st.spinner("Analyse en cours…"):
            raw = claude(prompt)
        data = parse_json(raw)
        if data:
            st.session_state.reformulation = data.get("reformulation", "")
            st.session_state.cynefin = data.get("cynefin", {})
            st.session_state.ambiguites = data.get("ambiguites", [])
            st.session_state.manques = data.get("manques", [])

    # ── Résultats ──
    if st.session_state.reformulation:
        st.divider()
        st.subheader("📊 Analyse de votre problème")

        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.markdown("**🔄 Reformulation proposée**")
            st.info(st.session_state.reformulation)

            if st.session_state.ambiguites:
                st.markdown("**⚠️ Ambiguïtés détectées**")
                for a in st.session_state.ambiguites:
                    st.warning(f"• {a}")

            if st.session_state.manques:
                st.markdown("**❓ Informations manquantes**")
                for m in st.session_state.manques:
                    st.error(f"• {m}")

        with col_b:
            st.markdown("**🧭 Nature du problème**")
            cyn = st.session_state.cynefin
            if isinstance(cyn, dict):
                cat = cyn.get("categorie", "Complexe")
                justif = cyn.get("justification", "")
            else:
                cat, justif = str(cyn), ""
            emoji, desc = CYNEFIN_INFO.get(cat, ("📌", cat))
            st.markdown(f"### {emoji} {cat}")
            st.caption(desc)
            if justif:
                st.caption(f"*{justif}*")

        st.markdown("**✏️ Ajustez la reformulation si nécessaire**")
        edited = st.text_area("Reformulation", value=st.session_state.reformulation, height=100,
                               label_visibility="collapsed")
        st.session_state.reformulation = edited

        st.button("✅ Valider et passer au Miroir des Impossibles →", type="primary", on_click=next_phase)


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 1 — MIROIR DES IMPOSSIBLES
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == 1:
    phase_header(
        "2", "Miroir des Impossibles",
        "Avant de cadrer votre sous-problème, un détour nécessaire."
    )

    st.info(f"**Domaine exploré** : {st.session_state.reformulation[:120]}…")

    st.markdown("""
> *"Les experts sont souvent les derniers à croire qu'une rupture est possible dans leur domaine —
> et les premiers à devoir l'intégrer une fois qu'elle arrive."*

Cette phase ne remet pas en cause votre expertise. Elle pose une seule question :
**existe-t-il des technologies ou approches venues d'autres domaines que vous n'avez pas encore considérées ?**
""")

    if st.button("🪞 Générer le Miroir des Impossibles", type="primary",
                 disabled=not API_KEY):
        prompt = f"""L'expert travaille sur ce problème de transition écologique :
"{st.session_state.reformulation}"

Génère 4 cas historiques réels où des experts reconnus d'un domaine ont déclaré qu'une technologie ou approche était impossible — et où ils avaient tort. Choisis des cas variés en termes de domaine (pas uniquement l'énergie), mais tous avec une analogie directe avec le problème décrit.

Pour chaque cas, fournis en JSON valide (aucun markdown) :
- "domaine_origine" : le domaine du cas historique (ex: "Aérospatial", "Médecine", "Informatique"...)
- "ce_que_les_experts_disaient" : la conviction des experts de l'époque en 1 phrase (ton affirmatif, passé)
- "ce_qui_s_est_passe" : ce qui s'est réellement passé en 1-2 phrases (rupture, technologie venue d'ailleurs...)
- "technologie_cle" : la technologie ou approche externe qui a rendu la chose possible
- "analogie_avec_le_probleme" : en 1 phrase, en quoi ce cas éclaire le problème de l'expert (lien direct, pas métaphorique)
- "question_miroir" : une question déstabilisante mais bienveillante que ce cas pose à l'expert sur son propre problème

Réponds UNIQUEMENT avec un JSON valide : {{ "cas": [ ... ] }}"""

        with st.spinner("Recherche de cas analogues…"):
            raw = claude(prompt, max_tokens=2000)
        data = parse_json(raw)
        if data:
            st.session_state.miroir_cas = data.get("cas", [])

    if st.session_state.miroir_cas:
        st.divider()
        st.subheader("📋 Cas historiques — ce que les experts disaient")

        for i, cas in enumerate(st.session_state.miroir_cas):
            with st.expander(
                f"**{cas.get('domaine_origine', '')}** — *\"{cas.get('ce_que_les_experts_disaient', '')}\"*",
                expanded=(i == 0)
            ):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**❌ Ce que les experts disaient**")
                    st.error(cas.get("ce_que_les_experts_disaient", ""))
                    st.markdown("**✅ Ce qui s'est passé**")
                    st.success(cas.get("ce_qui_s_est_passe", ""))
                with col_b:
                    st.markdown("**🔑 Technologie clé venue d'ailleurs**")
                    st.info(f"`{cas.get('technologie_cle', '')}`")
                    st.markdown("**🔗 Analogie avec votre problème**")
                    st.warning(cas.get("analogie_avec_le_probleme", ""))

                st.markdown(f"**❓ Question miroir pour vous :** *{cas.get('question_miroir', '')}*")

                # Réaction de l'expert
                reaction = st.text_area(
                    "Votre réaction / ce que ce cas vous inspire :",
                    value=st.session_state.miroir_reactions.get(f"cas_{i}", ""),
                    height=70,
                    key=f"reaction_{i}",
                    placeholder="Ce cas me fait penser que… / Dans mon domaine, l'équivalent serait…"
                )
                st.session_state.miroir_reactions[f"cas_{i}"] = reaction

        st.divider()
        st.subheader("💭 Votre leçon personnelle")
        st.caption(
            "En regardant ces cas ensemble : quelle conviction sur votre problème mérite d'être "
            "mise en question ? Pas pour l'abandonner — pour laisser de la place à l'inattendu."
        )
        lecon = st.text_area(
            "Leçon",
            value=st.session_state.miroir_lecon,
            height=100,
            label_visibility="collapsed",
            placeholder="Ex : Je réalise que je raisonne uniquement à partir des technologies actuelles de captation. Il existe peut-être des approches biologiques ou des matériaux que je n'ai pas explorés…"
        )
        st.session_state.miroir_lecon = lecon

        st.button("✅ Continuer vers le Scout Technologique →", type="primary", on_click=next_phase)


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 2 — SCOUT TECHNOLOGIQUE
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == 2:
    phase_header(
        "3", "Scout Technologique",
        "Quelles technologies venues d'autres domaines pourraient changer la donne ?"
    )

    st.info(f"**Problème** : {st.session_state.reformulation[:120]}…")
    if st.session_state.miroir_lecon:
        st.success(f"**Votre leçon du Miroir** : *{st.session_state.miroir_lecon}*")

    st.markdown("""
> Le DARPA finance des projets en imposant une règle : **aucun expert du domaine ne peut être
> chef de projet.** Non par mépris de l'expertise — mais pour forcer les connexions
> avec des technologies que seul un "outsider" oserait proposer.

Cette phase joue ce rôle : identifier des technologies ou méthodes récentes venues d'autres
champs qui pourraient s'appliquer à votre problème.
""")

    if st.button("🔭 Lancer le Scout Technologique", type="primary", disabled=not API_KEY):
        lecon_block = f"\nLeçon que l'expert tire du Miroir des Impossibles : {st.session_state.miroir_lecon}" if st.session_state.miroir_lecon else ""

        prompt = f"""L'expert travaille sur ce problème de transition écologique :
"{st.session_state.reformulation}"{lecon_block}

Joue le rôle d'un "scout technologique" : identifie 4 technologies ou approches récentes (post-2015) venues de domaines *extérieurs* à la transition écologique qui pourraient apporter une solution partielle ou totalement nouvelle à ce problème.

Domaines à explorer prioritairement : IA/ML, biologie synthétique, matériaux avancés, robotique, blockchain/DLT, sciences comportementales, médecine de précision, informatique quantique, impression 3D avancée, satellites/télédétection, edge computing.

Pour chaque technologie, fournis en JSON valide :
- "technologie" : nom précis de la technologie ou approche
- "domaine_origine" : domaine d'où elle vient
- "maturite" : "émergente" (TRL 1-4) | "en développement" (TRL 5-7) | "disponible" (TRL 8-9)
- "description" : 2 phrases — ce que c'est et ce qu'elle permet
- "application_possible" : 2-3 phrases — comment elle pourrait s'appliquer au problème de l'expert. Sois concret et direct.
- "sous_probleme_potentiel" : quel sous-problème spécifique cette technologie permettrait-elle d'aborder ?
- "risque_principal" : 1 phrase — le principal risque ou limite à date
- "exemple_concret" : 1 cas réel d'application (même dans un autre secteur que la transition écologique)

Réponds UNIQUEMENT avec un JSON valide : {{ "technologies": [ ... ] }}"""

        with st.spinner("Exploration en cours…"):
            raw = claude(prompt, max_tokens=4000)
        data = parse_json(raw)
        if data:
            st.session_state.scout_techs = data.get("technologies", [])

    if st.session_state.scout_techs:
        st.divider()
        st.subheader("🔭 Technologies candidates")
        st.caption("Pour chaque technologie : évaluez si elle ouvre un angle nouveau sur votre problème.")

        maturite_colors = {
            "émergente": ("🔴", "Émergente"),
            "en développement": ("🟡", "En développement"),
            "disponible": ("🟢", "Disponible"),
        }

        sel_ids = [t.get("technologie") for t in st.session_state.scout_selections]

        for tech in st.session_state.scout_techs:
            t_name = tech.get("technologie", "")
            mat = tech.get("maturite", "").lower()
            mat_e, mat_l = maturite_colors.get(mat, ("📌", mat))
            is_sel = t_name in sel_ids

            border = "border-left: 4px solid #1a7a4a;" if is_sel else "border-left: 4px solid #ddd;"
            sel_badge = " ✅" if is_sel else ""

            with st.container():
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(f"<div style='{border} padding-left:12px'>", unsafe_allow_html=True)
                    st.markdown(
                        f"**{t_name}**{sel_badge} — {mat_e} `{mat_l}` — *origine : {tech.get('domaine_origine', '')}*"
                    )
                    st.markdown(tech.get("description", ""))

                    col_app, col_risk = st.columns(2)
                    with col_app:
                        st.markdown("**🎯 Application possible**")
                        st.info(tech.get("application_possible", ""))
                        st.markdown(f"**📦 Sous-problème adressable :** *{tech.get('sous_probleme_potentiel', '')}*")
                    with col_risk:
                        st.markdown("**⚠️ Risque principal**")
                        st.warning(tech.get("risque_principal", ""))
                        st.markdown(f"**💡 Exemple réel :** {tech.get('exemple_concret', '')}")
                    st.markdown("</div>", unsafe_allow_html=True)

                with c2:
                    if is_sel:
                        if st.button("✖ Retirer", key=f"desel_t_{t_name}", use_container_width=True):
                            st.session_state.scout_selections = [
                                t for t in st.session_state.scout_selections
                                if t.get("technologie") != t_name
                            ]
                            st.rerun()
                    else:
                        if st.button("＋ Retenir", key=f"sel_t_{t_name}", use_container_width=True):
                            st.session_state.scout_selections.append(tech)
                            st.rerun()
                st.divider()

        # Synthèse et ouverture
        if st.session_state.scout_selections:
            st.subheader(f"✅ {len(st.session_state.scout_selections)} technologie(s) retenue(s)")
            for t in st.session_state.scout_selections:
                st.markdown(f"- **{t.get('technologie')}** ({t.get('maturite')}) → *{t.get('sous_probleme_potentiel', '')}*")

        st.divider()
        st.subheader("🔓 Comment cela change-t-il votre regard sur le problème ?")
        st.caption(
            "Pas besoin d'avoir choisi une technologie pour répondre. "
            "Même un 'aucune ne s'applique' est une information utile."
        )
        ouvertures = st.text_area(
            "Ouvertures",
            value=st.session_state.scout_ouvertures,
            height=100,
            label_visibility="collapsed",
            placeholder="Ex : Je n'avais pas envisagé que la télédétection satellite pourrait remplacer les capteurs terrain — cela ouvre la possibilité de couvrir 10x plus de sites avec le même budget…"
        )
        st.session_state.scout_ouvertures = ouvertures

        st.button("✅ Continuer vers la Décomposition →", type="primary", on_click=next_phase)


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 3 — DÉCOMPOSITION
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == 3:
    phase_header("4", "Décomposition", "Explorer les sous-problèmes possibles et choisir votre cible.")

    st.info(f"**Problème général** : {st.session_state.reformulation}")
    st.markdown("""
> Un problème général peut se décomposer de dizaines de façons selon l'acteur ciblé,
> le levier utilisé et l'horizon temporel. Cette phase vous oblige à **faire un choix**
> plutôt que de tout vouloir résoudre.
""")

    if st.button("🤖 Générer des sous-problèmes candidats", type="primary",
                 disabled=not API_KEY):

        # Contexte SofIA
        sofia_context = ""
        if st.session_state.get("sofia_data"):
            sd = st.session_state.sofia_data
            facts = [ex.get("reponse_sofia", "")[:500] for ex in sd.get("exchanges", [])]
            sofia_context = (
                "\n\nDONNÉES ADEME (issues de SofIA) :\n"
                + "\n---\n".join(facts[:3])
                + "\n\nUtilise ces données pour ancrer les sous-problèmes dans des objectifs réglementaires réels.\n"
            )

        # Contexte Scout Technologique
        scout_context = ""
        if st.session_state.scout_selections:
            techs = st.session_state.scout_selections
            scout_context = (
                "\n\nTECHNOLOGIES IDENTIFIÉES PAR LE SCOUT TECHNOLOGIQUE :\n"
                + "\n".join(
                    f"- {t.get('technologie')} ({t.get('domaine_origine')}) → "
                    f"Sous-problème potentiel : {t.get('sous_probleme_potentiel', '')}"
                    for t in techs
                )
                + "\n\nAu moins 1-2 des 6 sous-problèmes générés DOIVENT intégrer une de ces technologies "
                  "comme levier principal. Signale-le explicitement dans le champ 'tech_scout'.\n"
            )
        elif st.session_state.scout_ouvertures:
            scout_context = (
                f"\n\nOUVERTURES DE L'EXPERT APRÈS LE SCOUT : {st.session_state.scout_ouvertures}\n"
                "Intègre ces ouvertures dans au moins un sous-problème.\n"
            )

        prompt = f"""Problème général (transition écologique) :
"{st.session_state.reformulation}"{sofia_context}{scout_context}

Génère 6 sous-problèmes candidats distincts. Varie les angles :
- Acteur ciblé (entreprise, collectivité, citoyen, filière sectorielle...)
- Levier principal (technique, comportemental, réglementaire, économique, formation, data...)
- Temporalité (court terme <18 mois vs moyen terme 18-36 mois)

Pour chaque sous-problème, fournis :
- "id" : numéro de 1 à 6
- "titre" : titre court accrocheur (max 10 mots)
- "description" : 2 phrases précises. Cite un objectif chiffré ou une réglementation si pertinent.
- "acteur" : acteur principal ciblé
- "levier" : type de levier principal (1 mot)
- "temporalite" : "court" (<18 mois) ou "moyen" (18-36 mois)
- "ambition" : "locale", "sectorielle" ou "systémique"
- "pourquoi_pertinent" : 1 phrase avec données concrètes si disponibles
- "ancrage_ademe" : "oui" si ancré dans des objectifs ADEME, "non" sinon
- "tech_scout" : si ce sous-problème mobilise une technologie identifiée par le Scout, indiquer son nom — sinon null

Réponds UNIQUEMENT en JSON valide avec une clé "sous_problemes" contenant la liste.
"""
        with st.spinner("Génération des sous-problèmes…"):
            raw = claude(prompt, max_tokens=2500)
        data = parse_json(raw)
        if data:
            st.session_state.sub_problems = data.get("sous_problemes", [])

    if st.session_state.sub_problems:
        st.divider()

        sel_list = st.session_state.selected_sub_problems_list
        nb_sel = len(sel_list)
        sel_ids = [sp.get("id") for sp in sel_list]

        # ── Compteur de sélection ──
        if nb_sel == 0:
            st.info("☝️ Sélectionnez **1 ou 2 sous-problèmes** pour continuer. Avec 2 sélections, Claude les synthétisera en un sous-problème affiné.")
        elif nb_sel == 1:
            st.warning(f"**1/2 sélectionné** : *{sel_list[0].get('titre', '')}* — Sélectionnez un 2ᵉ pour une synthèse, ou validez directement.")
        else:
            st.success(f"**2/2 sélectionnés** : *{sel_list[0].get('titre', '')}* + *{sel_list[1].get('titre', '')}*")

        st.subheader("🗂️ Sous-problèmes candidats")

        levier_emojis = {
            "technique": "⚙️", "comportemental": "🧠", "réglementaire": "📋",
            "économique": "💰", "formation": "🎓", "data": "📊", "organisationnel": "🏗️"
        }

        for sp in st.session_state.sub_problems:
            sp_id = sp.get("id")
            is_selected = sp_id in sel_ids
            le = levier_emojis.get(sp.get("levier", "").lower(), "📌")
            te = "⏱️" if sp.get("temporalite") == "court" else "📅"
            ae = {"locale": "📍", "sectorielle": "🏭", "systémique": "🌍"}.get(sp.get("ambition", ""), "")
            ademe_badge = " 🏛️ *ancré ADEME*" if sp.get("ancrage_ademe") == "oui" else ""
            scout_badge = f" 🔭 *{sp.get('tech_scout')}*" if sp.get("tech_scout") else ""

            # Bordure verte si sélectionné
            border_style = "border-left: 4px solid #1a7a4a; padding-left: 12px;" if is_selected else "border-left: 4px solid #e0e0e0; padding-left: 12px;"
            sel_badge = " ✅ **SÉLECTIONNÉ**" if is_selected else ""

            with st.container():
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(
                        f"<div style='{border_style}'>",
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        f"**{sp_id}. {sp.get('titre', '')}** {le} {te} {ae}{ademe_badge}{scout_badge}{sel_badge}\n\n"
                        f"{sp.get('description', '')}\n\n"
                        f"`Acteur : {sp.get('acteur', '')}` &nbsp;|&nbsp; "
                        f"`Levier : {sp.get('levier', '')}` &nbsp;|&nbsp; "
                        f"`{sp.get('ambition', '')}` &nbsp;|&nbsp; "
                        f"`{sp.get('temporalite', '')} terme`\n\n"
                        f"*{sp.get('pourquoi_pertinent', '')}*"
                    )
                    st.markdown("</div>", unsafe_allow_html=True)

                with c2:
                    if is_selected:
                        if st.button("✖ Retirer", key=f"desel_{sp_id}", use_container_width=True):
                            st.session_state.selected_sub_problems_list = [
                                s for s in sel_list if s.get("id") != sp_id
                            ]
                            st.rerun()
                    else:
                        disabled = nb_sel >= 2
                        btn_label = "＋ Choisir" if nb_sel < 2 else "Max 2"
                        if st.button(btn_label, key=f"sel_{sp_id}",
                                     use_container_width=True, disabled=disabled):
                            st.session_state.selected_sub_problems_list.append(sp)
                            st.rerun()
                st.divider()

    # ── Zone de synthèse / validation ──────────────────────────────────────────
    sel_list = st.session_state.selected_sub_problems_list
    nb_sel = len(sel_list)

    if nb_sel == 2:
        st.subheader("🔀 Synthèse des 2 sous-problèmes")
        st.markdown(
            f"Vous avez sélectionné **{sel_list[0].get('titre', '')}** "
            f"et **{sel_list[1].get('titre', '')}**. "
            "Claude peut les synthétiser en un sous-problème plus précis qui capture "
            "le meilleur des deux angles, ou vous pouvez en choisir un seul."
        )

        col_synth, col_manual = st.columns(2)
        with col_synth:
            if st.button("🤖 Synthétiser les 2 en un sous-problème affiné", type="primary",
                         use_container_width=True, disabled=not API_KEY):
                sp1, sp2 = sel_list[0], sel_list[1]
                prompt_synth = f"""L'expert a sélectionné 2 sous-problèmes complémentaires dans le domaine de la transition écologique. Synthétise-les en un seul sous-problème affiné et cohérent.

PROBLÈME GÉNÉRAL : {st.session_state.reformulation}

SOUS-PROBLÈME A :
- Titre : {sp1.get('titre', '')}
- Description : {sp1.get('description', '')}
- Acteur : {sp1.get('acteur', '')} | Levier : {sp1.get('levier', '')} | {sp1.get('temporalite', '')} terme

SOUS-PROBLÈME B :
- Titre : {sp2.get('titre', '')}
- Description : {sp2.get('description', '')}
- Acteur : {sp2.get('acteur', '')} | Levier : {sp2.get('levier', '')} | {sp2.get('temporalite', '')} terme

Génère en JSON valide (aucun markdown) :
- "titre" : titre du sous-problème synthétisé (max 12 mots)
- "sous_probleme" : formulation complète en 3-4 phrases précises qui intègre les apports des deux angles
- "ce_qui_vient_de_A" : 1 phrase — ce que le sous-problème A apporte à la synthèse
- "ce_qui_vient_de_B" : 1 phrase — ce que le sous-problème B apporte à la synthèse
- "acteur" : acteur(s) principaux ciblés
- "levier" : levier(s) principal/principaux
- "gain_vs_choix_unique" : 1-2 phrases — pourquoi cette synthèse est meilleure que choisir l'un ou l'autre seul
"""
                with st.spinner("Synthèse en cours…"):
                    raw = claude(prompt_synth, max_tokens=1200)
                data = parse_json(raw)
                if data:
                    synth_text = (
                        f"[SYNTHÈSE] {data.get('titre', '')} : {data.get('sous_probleme', '')}"
                    )
                    st.session_state.selected_sub_problem = synth_text
                    st.session_state["_synth_data"] = data
                    st.rerun()

        with col_manual:
            st.caption("Ou choisissez lequel des deux conserver :")
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"Garder A\n*{sel_list[0].get('titre', '')[:25]}…*",
                             use_container_width=True):
                    sp = sel_list[0]
                    st.session_state.selected_sub_problem = f"{sp.get('titre', '')} : {sp.get('description', '')}"
                    st.session_state.selected_sub_problems_list = [sp]
                    st.rerun()
            with c2:
                if st.button(f"Garder B\n*{sel_list[1].get('titre', '')[:25]}…*",
                             use_container_width=True):
                    sp = sel_list[1]
                    st.session_state.selected_sub_problem = f"{sp.get('titre', '')} : {sp.get('description', '')}"
                    st.session_state.selected_sub_problems_list = [sp]
                    st.rerun()

        # Affichage résultat de synthèse
        if st.session_state.get("_synth_data"):
            sd = st.session_state["_synth_data"]
            st.markdown(f"""
<div class="hmw-box" style="margin-top:16px">
  <p style="color:#a8d8ea; margin:0 0 6px 0; font-size:0.85rem; text-transform:uppercase; letter-spacing:1px">Sous-problème synthétisé</p>
  <h3 style="font-size:1.1rem">{sd.get('titre', '')}</h3>
  <p style="color:#d4f5e9; margin:8px 0 0 0; font-size:0.95rem">{sd.get('sous_probleme', '')}</p>
</div>
""", unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            with col_a:
                st.caption(f"**Apport de A :** {sd.get('ce_qui_vient_de_A', '')}")
            with col_b:
                st.caption(f"**Apport de B :** {sd.get('ce_qui_vient_de_B', '')}")
            if sd.get("gain_vs_choix_unique"):
                st.info(f"💡 {sd['gain_vs_choix_unique']}")

    elif nb_sel == 1:
        sp = sel_list[0]
        # On ne pré-remplit qu'au moment où la sélection change (sinon on écraserait
        # les ajustements de l'expert, notamment en revenant sur cette étape)
        if st.session_state.get("_sel_sig") != sp.get("id"):
            st.session_state.selected_sub_problem = f"{sp.get('titre', '')} : {sp.get('description', '')}"
            st.session_state["_sel_sig"] = sp.get("id")
    else:
        st.session_state["_sel_sig"] = None

    # ── Formulation manuelle (toujours disponible) ────────────────────────────
    st.subheader("✍️ Formulation finale — ajustez si nécessaire")
    custom = st.text_area(
        "Votre sous-problème",
        value=st.session_state.selected_sub_problem,
        height=120,
        placeholder="Décrivez précisément le sous-problème que vous souhaitez résoudre...",
        label_visibility="collapsed"
    )
    st.session_state.selected_sub_problem = custom

    if st.session_state.selected_sub_problem.strip():
        st.success(f"**Sous-problème retenu** : {st.session_state.selected_sub_problem}")
        st.button("✅ Valider et décrire mes ressources →", type="primary", on_click=next_phase)


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 4 — RESSOURCES & CONTRAINTES
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == 4:
    phase_header("5", "Ressources & Contraintes", "Plus vous êtes précis ici, plus le test de cohérence sera utile.")

    st.info(f"**Sous-problème** : {st.session_state.selected_sub_problem}")

    st.markdown("""
> C'est souvent ici que les projets déraillent : les objectifs sont calibrés sur l'ambition,
> pas sur les moyens réels. Soyez honnête — cet outil ne juge pas, il vous aide.
""")

    r = st.session_state.resources
    c = st.session_state.constraints

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💰 Budget")
        budget_total      = st.number_input("Budget total (€)", min_value=0, step=10_000,
                                             value=int(r.get("budget", 0)))
        budget_rh         = st.number_input("Dont masse salariale / RH (€)", min_value=0, step=5_000,
                                             value=int(r.get("budget_rh", 0)))
        budget_prestation = st.number_input("Dont prestations externes (€)", min_value=0, step=5_000,
                                             value=int(r.get("budget_prestation", 0)))

        st.subheader("👥 Équipe")
        etp = st.number_input("ETP dédiés au projet", min_value=0.0, step=0.5,
                               value=float(r.get("etp", 0.5)))
        competences = st.multiselect(
            "Compétences disponibles en interne",
            ["Ingénierie / technique", "Data / IA", "Sciences comportementales",
             "Communication / sensibilisation", "Droit / réglementation",
             "Finance / économie", "Sciences naturelles / écologie",
             "Management de projet", "Concertation / participation citoyenne"],
            default=r.get("competences", [])
        )
        competences_manquantes = st.text_area(
            "Compétences manquantes (à recruter ou sous-traiter)",
            value=r.get("competences_manquantes", ""),
            height=80,
            placeholder="Ex: expertise juridique en droit environnemental, data scientist..."
        )

    with col2:
        st.subheader("⏱️ Contraintes temporelles")
        duree_mois = st.slider("Durée totale du projet (mois)", 6, 60,
                               value=int(c.get("duree_mois", 36)))
        jalon_mois = st.slider("Premier jalon / résultats intermédiaires attendus (mois)", 3, 36,
                               value=int(c.get("jalon_mois", 18)))

        st.subheader("🎯 Objectifs attendus")
        objectif_principal = st.text_area(
            "Objectif principal (chiffré si possible)",
            value=c.get("objectif_principal", ""),
            height=80,
            placeholder="Ex: Réduire de 20% les émissions GES du secteur X sur le territoire Y d'ici 2027"
        )
        objectif_secondaire = st.text_area(
            "Objectifs secondaires",
            value=c.get("objectif_secondaire", ""),
            height=60,
            placeholder="Ex: Former 50 entreprises, créer un outil de mesure réplicable..."
        )

        st.subheader("🤝 Partenaires & Historique")
        partenaires_imposes = st.text_area(
            "Partenaires obligatoires (imposés par le financement ou la gouvernance)",
            value=c.get("partenaires_imposes", ""),
            height=60,
            placeholder="Ex: ADEME, Région X, Fédération professionnelle Y..."
        )
        partenaires_potentiels = st.text_area(
            "Partenaires potentiels (à mobiliser)",
            value=c.get("partenaires_potentiels", ""),
            height=60
        )
        deja_tente = st.text_area(
            "Ce qui a déjà été tenté sur ce problème (et pourquoi ça n'a pas suffi)",
            value=c.get("deja_tente", ""),
            height=80,
            placeholder="Ex: Campagne de sensibilisation en 2021 → faible adoption car pas de levier économique associé..."
        )

    # Enregistrement à chaque modification (pour ne rien perdre en revenant en arrière)
    st.session_state.resources = {
        "budget": budget_total, "budget_rh": budget_rh,
        "budget_prestation": budget_prestation, "etp": etp,
        "competences": competences, "competences_manquantes": competences_manquantes,
    }
    st.session_state.constraints = {
        "duree_mois": duree_mois, "jalon_mois": jalon_mois,
        "objectif_principal": objectif_principal, "objectif_secondaire": objectif_secondaire,
        "partenaires_imposes": partenaires_imposes, "partenaires_potentiels": partenaires_potentiels,
        "deja_tente": deja_tente,
    }

    st.divider()

    st.button("✅ Valider et tester la cohérence →", type="primary", on_click=next_phase)


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 5 — TEST DE COHÉRENCE
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == 5:
    phase_header("6", "Test de Cohérence", "Votre sous-problème est-il réellement à votre portée ?")

    r = st.session_state.resources
    c = st.session_state.constraints

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Budget total", f"{r.get('budget', 0):,.0f} €")
    col2.metric("👥 ETP", f"{r.get('etp', 0)}")
    col3.metric("📅 Durée", f"{c.get('duree_mois', 0)} mois")
    col4.metric("⏱️ 1er jalon", f"{c.get('jalon_mois', 0)} mois")

    st.info(f"**Sous-problème évalué** : {st.session_state.selected_sub_problem}")

    if st.button("🔬 Lancer le test de cohérence", type="primary",
                 disabled=not API_KEY):
        prompt = f"""Tu évalues la cohérence entre un sous-problème de transition écologique et les ressources disponibles.

SOUS-PROBLÈME : {st.session_state.selected_sub_problem}
PROBLÈME GÉNÉRAL : {st.session_state.reformulation}

RESSOURCES :
- Budget total : {r.get('budget', 0):,}€ (RH : {r.get('budget_rh', 0):,}€ | Prestations : {r.get('budget_prestation', 0):,}€)
- ETP : {r.get('etp', 0)}
- Compétences internes : {', '.join(r.get('competences', [])) or 'Non précisé'}
- Compétences manquantes : {r.get('competences_manquantes', 'Non précisé')}

CONTRAINTES :
- Durée totale : {c.get('duree_mois', 0)} mois
- Premier jalon : {c.get('jalon_mois', 0)} mois
- Objectif principal : {c.get('objectif_principal', 'Non précisé')}
- Partenaires obligatoires : {c.get('partenaires_imposes', 'Aucun')}
- Déjà tenté : {c.get('deja_tente', 'Rien de connu')}

Évalue selon 4 critères, chacun noté de 0 à 25 :

1. "mesurabilite" — Les objectifs sont-ils mesurables avec ces moyens ? Des KPIs clairs sont-ils définissables ?
2. "jalons" — Un résultat concret est-il réaliste dans le délai du premier jalon (apprentissage, prototype, données) ?
3. "competences" — Les compétences disponibles couvrent-elles les leviers nécessaires ? Les manques sont-ils gérables ?
4. "precedents" — Existe-t-il dans la bibliographie ou la pratique des projets comparables à ce niveau de ressources ?

Pour chaque critère :
- "score" : 0 à 25
- "commentaire" : 2-3 phrases d'analyse honnête
- "recommandation" : 1 action corrective concrète si score < 15 (sinon null)

Ajoute aussi :
- "score_global" : somme des 4 scores (0-100)
- "verdict" : "Cohérent" (70-100) | "Ajustements nécessaires" (40-69) | "Recadrage fort recommandé" (0-39)
- "analyse_risques" : 2-3 phrases sur les principaux risques de ce sous-problème avec ces ressources
- "recadrage_suggere" : Si verdict ≠ "Cohérent", propose un sous-problème plus ajusté (sinon null)

Réponds UNIQUEMENT en JSON valide. Aucun markdown, aucun backtick.
"""
        with st.spinner("Analyse de cohérence en cours…"):
            raw = claude(prompt, system=(
                "Tu es un expert rigoureux en évaluation de projets de transition écologique. "
                "Tu donnes des verdicts honnêtes et constructifs. Tu réponds en JSON valide uniquement."
            ), max_tokens=2500)
        data = parse_json(raw)
        if data:
            st.session_state.coherence_score = data.get("score_global", 0)
            st.session_state.coherence_details = data

    # ── Résultats ──
    if st.session_state.coherence_score is not None:
        d = st.session_state.coherence_details
        score = st.session_state.coherence_score
        verdict = d.get("verdict", "")
        emoji = score_emoji(score)

        st.divider()

        # Score global centré
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            st.markdown(f"""
<div class="score-box">
  <h1 style="font-size:3rem; margin:0">{emoji} {score}<span style="font-size:1.5rem">/100</span></h1>
  <h3 style="margin:8px 0 0 0">Verdict : {verdict}</h3>
</div>
""", unsafe_allow_html=True)

        st.divider()

        # Détail par critère
        st.subheader("📊 Détail par critère")
        criteres = [
            ("mesurabilite",  "📏 Mesurabilité des objectifs"),
            ("jalons",        "📅 Faisabilité du premier jalon"),
            ("competences",   "🧠 Adéquation des compétences"),
            ("precedents",    "📚 Précédents comparables"),
        ]
        for key, label in criteres:
            crit = d.get(key, {})
            if isinstance(crit, dict):
                s = crit.get("score", 0)
                comment = crit.get("commentaire", "")
                reco = crit.get("recommandation", "")
                se = score_emoji(s, max_s=25)
                with st.container():
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        st.metric(label, f"{se} {s}/25")
                    with c2:
                        st.markdown(comment)
                        if reco:
                            st.info(f"💡 {reco}")
                st.divider()

        # Analyse risques
        if d.get("analyse_risques"):
            st.subheader("⚠️ Analyse des risques")
            st.warning(d["analyse_risques"])

        # Recadrage
        recadrage = d.get("recadrage_suggere")
        if recadrage and verdict != "Cohérent":
            st.subheader("🔄 Recadrage suggéré par Claude")
            st.markdown(f"> {recadrage}")
            if st.button("↩️ Adopter ce recadrage (retour à la Décomposition)"):
                st.session_state.selected_sub_problem = recadrage
                go_phase(3)

        st.button("✅ Valider et passer à la Formulation Finale →", type="primary", on_click=next_phase)


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 6 — FORMULATION FINALE & EXPORT
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == 6:
    phase_header("7", "Formulation Finale", "Votre 'bon' sous-problème formulé, documenté et prêt à l'action.")

    # ── Raccourci : l'expert a déjà un problème bien formulé ──
    with st.expander("✍️ Vous avez déjà un problème bien formulé ? Saisissez-le directement",
                     expanded=st.session_state.get("_direct_entry", False)):
        st.caption("Pour chercher directement les communs, solutions, acteurs et données ouvertes "
                   "liés à votre problème, sans passer par les phases 1 à 6.")
        direct_pb = st.text_area(
            "Votre problème",
            value=st.session_state.hmw if st.session_state.get("_direct_entry") else "",
            height=120,
            placeholder="Ex : Comment pourrions-nous doubler le covoiturage domicile-travail dans "
                        "les territoires ruraux du Grand Est d'ici 2027 ?",
        )
        direct_ctx = st.text_area(
            "Contexte (facultatif) : territoire, public, contraintes…", height=80,
            value=(st.session_state.final_data or {}).get("contexte", "") if st.session_state.get("_direct_entry") else "",
        )
        direct_kpis = st.text_area(
            "Indicateurs de succès (facultatif, un par ligne)", height=80,
            placeholder="Ex : Nombre de trajets covoiturés par mois\nPart modale de la voiture solo",
        )
        if st.button("🔎 Utiliser ce problème et chercher des ressources →", type="primary",
                     disabled=not direct_pb.strip()):
            st.session_state.hmw = direct_pb.strip()
            st.session_state.final_data = {
                "formulation_complete": (direct_pb.strip() + ("\n\nContexte : " + direct_ctx.strip()
                                                             if direct_ctx.strip() else "")),
                "contexte": direct_ctx.strip(),
                "indicateurs_succes": [{"kpi": k} for k in _split_list(direct_kpis.replace(",", " "))
                                       if k] if direct_kpis.strip() else [],
            }
            if not st.session_state.selected_sub_problem:
                st.session_state.selected_sub_problem = direct_pb.strip()
            st.session_state["_direct_entry"] = True
            reset_exploration()
            set_phase(7)
            st.rerun()

    if st.session_state.coherence_score is not None:
        score = st.session_state.coherence_score or 0
        emoji = score_emoji(score)
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            st.metric(f"{emoji} Score de cohérence final", f"{score}/100",
                      delta=st.session_state.coherence_details.get("verdict", ""))
    else:
        score = 0

    st.divider()

    if st.button("✨ Générer la formulation finale", type="primary",
                 disabled=not API_KEY):
        r = st.session_state.resources
        c = st.session_state.constraints

        prompt = f"""Synthétise le travail réalisé pour formuler le "bon" sous-problème final.

PROBLÈME GÉNÉRAL : {st.session_state.reformulation}
SOUS-PROBLÈME RETENU : {st.session_state.selected_sub_problem}
SCORE DE COHÉRENCE : {score}/100 — {st.session_state.coherence_details.get("verdict", "")}

RESSOURCES : Budget {r.get('budget', 0):,}€ | {r.get('etp', 0)} ETP | {c.get('duree_mois', 0)} mois
OBJECTIF PRINCIPAL : {c.get('objectif_principal', 'Non précisé')}

Génère en JSON valide (aucun markdown, aucun backtick) avec EXACTEMENT cette structure :

"hmw" : string — Formulation "Comment pourrions-nous..." en 1-2 phrases (qui agit, levier, cible, objectif chiffré, délai)

"formulation_complete" : string — Brief de problème en 3-4 phrases

"indicateurs_succes" : liste de 4-5 objets, chacun avec :
  {{ "kpi": "nom de l'indicateur", "cible": "valeur cible chiffrée", "unite": "unité de mesure", "echeance": "délai" }}

"prochaines_etapes" : liste de 3 objets, chacun avec :
  {{ "action": "intitulé court de l'action", "description": "détail opérationnel en 1-2 phrases", "responsable": "qui porte cette action", "echeance": "ex: J+15 ou Mois 1", "livrable": "livrable concret attendu" }}

"risques_principaux" : liste de 3 objets, chacun avec :
  {{ "risque": "intitulé du risque", "mitigation": "action de mitigation concrète" }}

"questions_restantes" : liste de 2-3 objets, chacun avec :
  {{ "question": "la question à résoudre", "enjeu": "pourquoi c'est important", "moment_resolution": "quand doit-elle être tranchée" }}
"""
        with st.spinner("Formulation en cours…"):
            raw = claude(prompt, max_tokens=2500)
        data = parse_json(raw)
        if data:
            st.session_state.hmw = data.get("hmw", "")
            st.session_state.final_data = data
            st.session_state["_direct_entry"] = False
            reset_exploration()

    if st.session_state.hmw:
        fd = st.session_state.final_data

        # HMW box
        st.markdown(f"""
<div class="hmw-box">
  <p style="color:#a8d8ea; margin:0 0 8px 0; font-size:0.9rem; text-transform:uppercase; letter-spacing:1px">
    Comment pourrions-nous…
  </p>
  <h3>{st.session_state.hmw}</h3>
</div>
""", unsafe_allow_html=True)

        st.markdown(f"**Formulation complète :** {fd.get('formulation_complete', '')}")

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            # ── KPIs ──
            st.subheader("📏 Indicateurs de succès (KPIs)")
            for kpi in fd.get("indicateurs_succes", []):
                if isinstance(kpi, dict):
                    cible = kpi.get("cible", "")
                    unite = kpi.get("unite", "")
                    echeance = kpi.get("echeance", "")
                    st.markdown(
                        f"**{kpi.get('kpi', '')}**  \n"
                        f"🎯 `{cible} {unite}` — ⏱ {echeance}"
                    )
                else:
                    st.markdown(f"• {kpi}")
                st.divider()

            # ── Actions J+30 ──
            st.subheader("⚡ 3 premières actions (J+30)")
            for i, action in enumerate(fd.get("prochaines_etapes", []), 1):
                if isinstance(action, dict):
                    with st.container():
                        st.markdown(
                            f"**{i}. {action.get('action', '')}** "
                            f"— ⏱ `{action.get('echeance', '')}` "
                            f"— 👤 *{action.get('responsable', '')}*"
                        )
                        if action.get("description"):
                            st.caption(action["description"])
                        if action.get("livrable"):
                            st.info(f"📄 Livrable : {action['livrable']}", icon=None)
                else:
                    st.markdown(f"**{i}.** {action}")
                st.divider()

        with col2:
            # ── Risques ──
            st.subheader("⚠️ Risques & mitigations")
            for risk in fd.get("risques_principaux", []):
                if isinstance(risk, dict):
                    st.warning(f"**{risk.get('risque', '')}**")
                    if risk.get("mitigation"):
                        st.caption(f"💡 {risk['mitigation']}")
                else:
                    st.warning(f"• {risk}")

            # ── Questions restantes ──
            if fd.get("questions_restantes"):
                st.subheader("❓ Questions à trancher en cours de projet")
                for q in fd.get("questions_restantes", []):
                    if isinstance(q, dict):
                        with st.expander(f"❓ {q.get('question', '')}"):
                            if q.get("enjeu"):
                                st.markdown(f"**Enjeu :** {q['enjeu']}")
                            if q.get("moment_resolution"):
                                st.markdown(f"**À trancher :** *{q['moment_resolution']}*")
                    else:
                        st.info(f"• {q}")

        st.divider()

        # ── EXPORT ──────────────────────────────────────────────────
        st.subheader("📥 Exporter votre fiche")

        col_a, col_b = st.columns(2)

        # Export DOCX
        with col_a:
            if st.button("📄 Générer la fiche Word (.docx)", use_container_width=True, type="primary"):
                try:
                    from docx import Document as Doc
                    from docx.shared import Pt, RGBColor
                    from docx.enum.text import WD_ALIGN_PARAGRAPH

                    r = st.session_state.resources
                    c = st.session_state.constraints
                    d = st.session_state.coherence_details

                    document = Doc()

                    # Styles de base
                    style = document.styles["Normal"]
                    style.font.name = "Calibri"
                    style.font.size = Pt(11)

                    # Titre
                    title_p = document.add_heading("Fiche de Problème Stratégique", 0)
                    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    sub_p = document.add_paragraph(
                        f"Générée le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
                    )
                    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    document.add_paragraph("")

                    # 1. HMW
                    document.add_heading("1. Formulation « Comment Pourrions-Nous »", level=1)
                    p = document.add_paragraph(st.session_state.hmw)
                    p.runs[0].bold = True

                    # 2. Formulation complète
                    document.add_heading("2. Formulation Complète du Sous-Problème", level=1)
                    document.add_paragraph(fd.get("formulation_complete", ""))

                    # 3. Problème général
                    document.add_heading("3. Problème Général d'origine", level=1)
                    document.add_paragraph(st.session_state.reformulation)

                    # 4. Score de cohérence
                    document.add_heading("4. Score de Cohérence", level=1)
                    score_v = st.session_state.coherence_score
                    verdict_v = d.get("verdict", "")
                    document.add_paragraph(f"Score global : {score_v}/100  —  Verdict : {verdict_v}")

                    for key, label in [
                        ("mesurabilite", "Mesurabilité"),
                        ("jalons", "Faisabilité jalons"),
                        ("competences", "Compétences"),
                        ("precedents", "Précédents"),
                    ]:
                        crit = d.get(key, {})
                        if isinstance(crit, dict):
                            document.add_paragraph(
                                f"  • {label} : {crit.get('score', 0)}/25 — {crit.get('commentaire', '')}"
                            )

                    # 5. Ressources
                    document.add_heading("5. Ressources & Contraintes", level=1)
                    table = document.add_table(rows=7, cols=2)
                    table.style = "Table Grid"
                    rows_data = [
                        ("Budget total", f"{r.get('budget', 0):,.0f} €"),
                        ("Masse salariale / RH", f"{r.get('budget_rh', 0):,.0f} €"),
                        ("Prestations externes", f"{r.get('budget_prestation', 0):,.0f} €"),
                        ("ETP dédiés", str(r.get("etp", 0))),
                        ("Durée totale", f"{c.get('duree_mois', 0)} mois"),
                        ("Premier jalon", f"{c.get('jalon_mois', 0)} mois"),
                        ("Partenaires obligatoires", c.get("partenaires_imposes", "Aucun")),
                    ]
                    for i, (k, v) in enumerate(rows_data):
                        table.rows[i].cells[0].text = k
                        table.rows[i].cells[1].text = v

                    # 6. Objectif
                    document.add_heading("6. Objectif Principal", level=1)
                    document.add_paragraph(c.get("objectif_principal", "Non précisé"))
                    if c.get("objectif_secondaire"):
                        document.add_heading("Objectifs secondaires", level=2)
                        document.add_paragraph(c.get("objectif_secondaire"))

                    # 7. KPIs
                    document.add_heading("7. Indicateurs de Succès (KPIs)", level=1)
                    for kpi in fd.get("indicateurs_succes", []):
                        if isinstance(kpi, dict):
                            document.add_paragraph(
                                f"• {kpi.get('kpi', '')} : {kpi.get('cible', '')} {kpi.get('unite', '')} "
                                f"— Échéance : {kpi.get('echeance', '')}"
                            )
                        else:
                            document.add_paragraph(f"• {kpi}")

                    # 8. Actions J+30
                    document.add_heading("8. Prochaines Étapes (J+30)", level=1)
                    for i, action in enumerate(fd.get("prochaines_etapes", []), 1):
                        if isinstance(action, dict):
                            p = document.add_paragraph(style="List Number")
                            p.add_run(f"{action.get('action', '')}").bold = True
                            document.add_paragraph(
                                f"   {action.get('description', '')}\n"
                                f"   Responsable : {action.get('responsable', '')}  |  "
                                f"Échéance : {action.get('echeance', '')}  |  "
                                f"Livrable : {action.get('livrable', '')}"
                            )
                        else:
                            document.add_paragraph(f"{i}. {action}")

                    # 9. Risques
                    document.add_heading("9. Risques Principaux", level=1)
                    for risk in fd.get("risques_principaux", []):
                        if isinstance(risk, dict):
                            document.add_paragraph(
                                f"• {risk.get('risque', '')} → Mitigation : {risk.get('mitigation', '')}"
                            )
                        else:
                            document.add_paragraph(f"• {risk}")

                    # 10. Questions restantes
                    if fd.get("questions_restantes"):
                        document.add_heading("10. Questions à Trancher en Cours de Projet", level=1)
                        for q in fd.get("questions_restantes", []):
                            if isinstance(q, dict):
                                document.add_paragraph(
                                    f"• {q.get('question', '')}\n"
                                    f"   Enjeu : {q.get('enjeu', '')}\n"
                                    f"   À trancher : {q.get('moment_resolution', '')}"
                                )
                            else:
                                document.add_paragraph(f"• {q}")

                    buf = io.BytesIO()
                    document.save(buf)
                    buf.seek(0)

                    st.download_button(
                        label="⬇️ Télécharger la fiche Word",
                        data=buf.getvalue(),
                        file_name=f"fiche_sous_probleme_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )

                except ImportError:
                    st.error("python-docx non installé. Lancez : `pip install python-docx`")
                except Exception as e:
                    st.error(f"Erreur génération DOCX : {e}")

        # Export JSON
        with col_b:
            export = {
                "meta": {"date": datetime.now().isoformat(), "version": "1.0"},
                "probleme_general": st.session_state.reformulation,
                "sous_probleme_retenu": st.session_state.selected_sub_problem,
                "formulation_hmw": st.session_state.hmw,
                "formulation_complete": fd.get("formulation_complete", ""),
                "coherence": {
                    "score": st.session_state.coherence_score,
                    "verdict": st.session_state.coherence_details.get("verdict", ""),
                    "detail": {
                        k: st.session_state.coherence_details.get(k, {})
                        for k in ("mesurabilite", "jalons", "competences", "precedents")
                    },
                },
                "ressources": st.session_state.resources,
                "contraintes": st.session_state.constraints,
                "indicateurs_succes": fd.get("indicateurs_succes", []),
                "prochaines_etapes": fd.get("prochaines_etapes", []),
                "risques": fd.get("risques_principaux", []),
                "questions_restantes": fd.get("questions_restantes", []),
            }
            st.download_button(
                label="⬇️ Exporter en JSON",
                data=json.dumps(export, ensure_ascii=False, indent=2),
                file_name=f"sous_probleme_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.info(
            "💾 **Conservez votre problème formulé** : cliquez sur « Sauvegarder ma progression » "
            "ci-dessous. En rechargeant ce fichier plus tard (barre latérale → Reprendre un "
            "travail), vous reviendrez directement ici, sans refaire les phases 1 à 6."
        )

        st.divider()
        st.success("""
✅ **Félicitations !** Vous avez formulé votre "bon" sous-problème.

Cette fiche est votre référence de projet. Si le score de cohérence est sous 70, revoyez
le périmètre avant de vous lancer. Un bon problème bien formulé, c'est déjà 50% du travail.
        """)

        st.markdown("**Et maintenant ?** Avant d'agir, regardez ce qui existe déjà : communs, "
                    "solutions déployées, acteurs et données ouvertes liés à votre problème.")
        st.button("🔎 Explorer ce qui existe déjà →", type="primary", on_click=next_phase)


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 7 — COMMUNS & RESSOURCES (wiki de la Fabrique des Mobilités)
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == 7:
    phase_header("8", "Communs & Ressources",
                 "Communs, projets, acteurs et connaissances du wiki de la Fabrique des Mobilités.")

    if require_problem():
        st.markdown("""
> *Ne pas réinventer la roue.* Le [wiki de la Fabrique des Mobilités](https://wiki.lafabriquedesmobilites.fr)
> recense des **communs** (logiciels, données, méthodes réutilisables), des **projets**, des **acteurs**
> et des **connaissances**. Cette phase repère ceux qui concernent votre problème.
""")
        keywords_editor()

        if st.button("🔎 Rechercher dans le wiki", type="primary", disabled=not API_KEY):
            if ensure_keywords():
                try:
                    with st.spinner("Interrogation du wiki (environ 2 500 fiches)…"):
                        cands = sources.wiki_candidates(st.session_state.mots_cles)
                except Exception as e:  # noqa: BLE001
                    show_source_error("Le wiki de la Fabrique des Mobilités", e)
                    cands = None
                if cands is not None:
                    flat = [c for lst in cands.values() for c in lst]

                    def wsum(c):
                        bits = [c["type"], c["titre"]]
                        if c.get("description"):
                            bits.append(c["description"][:200])
                        if c.get("tags"):
                            bits.append("tags : " + ", ".join(c["tags"][:8]))
                        if c.get("themes"):
                            bits.append("thèmes : " + ", ".join(c["themes"][:5]))
                        return " | ".join(bits)

                    sel, synth = rank_with_claude(
                        flat, "fiches du wiki (communs, projets, acteurs, connaissances)", wsum,
                        "jusqu'à 4 par type (Commun, Projet, Acteur, Connaissance)")
                    res = {t: [x for x in sel if x["type"] == t] for t in sources.WIKI_TYPES}
                    st.session_state.wiki_results = res
                    st.session_state.wiki_synthese = synth
                    if not sel:
                        st.warning("Aucune fiche pertinente trouvée. Essayez d'ajuster les mots-clés.")

        res = st.session_state.wiki_results
        if any(res.values()):
            st.divider()
            if st.session_state.wiki_synthese:
                st.success(f"💡 {st.session_state.wiki_synthese}")
            labels = {"Commun": "🧩 Communs", "Projet": "🚀 Projets",
                      "Acteur": "👥 Acteurs", "Connaissance": "📚 Connaissances"}
            tabs = st.tabs([f"{labels[t]} ({len(res.get(t, []))})" for t in sources.WIKI_TYPES])
            for tab, t in zip(tabs, sources.WIKI_TYPES):
                with tab:
                    if not res.get(t):
                        st.caption("Rien de pertinent trouvé dans cette catégorie.")
                    for item in res.get(t, []):
                        show_item(item, "Wiki FabMob – " + t, [
                            item.get("description", "")[:160],
                            ("Thèmes : " + ", ".join(item.get("themes", [])[:3])) if item.get("themes") else "",
                        ])
            st.caption("Cochez « Retenir » pour ajouter une ressource à votre fiche finale (phase 11).")
            st.button("✅ Continuer vers les solutions France Mobilités →", type="primary", on_click=next_phase)
        else:
            st.button("Passer cette étape →", on_click=next_phase)


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 8 — SOLUTIONS & ACTEURS (France Mobilités)
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == 8:
    phase_header("9", "Solutions & Acteurs",
                 "Solutions déjà déployées en France et les acteurs qui les portent.")

    if require_problem():
        st.markdown("""
> [France Mobilités](https://www.francemobilites.fr/solutions) recense près de 900 solutions de mobilité
> (services, outils, dispositifs) avec leur porteur, leur maturité et les territoires concernés.
""")
        keywords_editor()

        if st.button("🔎 Rechercher sur France Mobilités", type="primary", disabled=not API_KEY):
            if ensure_keywords():
                try:
                    with st.spinner("Chargement du catalogue France Mobilités…"):
                        cands = sources.fm_candidates(st.session_state.mots_cles)
                except Exception as e:  # noqa: BLE001
                    show_source_error("France Mobilités", e)
                    cands = None
                if cands is not None:
                    def fsum(c):
                        return " | ".join(x for x in [
                            c["titre"], c.get("sous_titre", "")[:160], c.get("description", "")[:200],
                            "porteur : " + c.get("porteur", ""), "maturité : " + c.get("maturite", ""),
                            "thèmes : " + ", ".join(c.get("themes", [])),
                            "territoires : " + ", ".join(c.get("territoires", [])),
                        ] if x)

                    sel, synth = rank_with_claude(
                        cands, "solutions France Mobilités", fsum, "jusqu'à 8",
                        extra=" Privilégie la diversité des approches et des porteurs.")
                    st.session_state.fm_results = sel
                    st.session_state.fm_synthese = synth
                    if not sel:
                        st.warning("Aucune solution pertinente trouvée. Essayez d'ajuster les mots-clés.")

        sel = st.session_state.fm_results
        if sel:
            st.divider()
            if st.session_state.fm_synthese:
                st.success(f"💡 {st.session_state.fm_synthese}")
            st.subheader(f"🛠️ {len(sel)} solution(s) liée(s) à votre problème")
            st.caption("Source : [France Mobilités](https://www.francemobilites.fr/solutions). "
                       "Chaque titre renvoie vers la fiche d'origine sur francemobilites.fr.")
            for item in sel:
                show_item(item, "France Mobilités", [
                    item.get("sous_titre", "")[:160],
                    f"Porteur : {item.get('porteur', '')}" if item.get("porteur") else "",
                    f"Maturité : {item.get('maturite', '')}" if item.get("maturite") else "",
                    f"Mise à jour : {item.get('maj', '')}" if item.get("maj") else "",
                ])

            # Acteurs : les porteurs des solutions sélectionnées
            acteurs = {}
            for item in sel:
                if item.get("porteur"):
                    acteurs.setdefault(item["porteur"], {"url": item.get("porteur_url", ""), "solutions": []})
                    acteurs[item["porteur"]]["solutions"].append(item["titre"])
            if acteurs:
                st.subheader("👥 Acteurs à contacter")
                for nom, a in acteurs.items():
                    lien = f"[{nom}]({a['url']})" if a["url"] else nom
                    st.markdown(f"- **{lien}** — {', '.join(a['solutions'])}")
            st.button("✅ Continuer vers les données ouvertes →", type="primary", on_click=next_phase)
        else:
            st.button("Passer cette étape →", on_click=next_phase)


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 9 — DONNÉES OUVERTES (data.gouv.fr + INSEE)
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == 9:
    phase_header("10", "Données Ouvertes",
                 "Les données publiques pour objectiver le problème et suivre vos indicateurs.")

    if require_problem():
        kpis = [k.get("kpi", "") for k in (st.session_state.final_data or {}).get("indicateurs_succes", [])
                if isinstance(k, dict)]
        st.markdown("""
> Des données ouvertes existent peut-être déjà pour **mesurer la situation de départ** et **suivre vos
> indicateurs** : [data.gouv.fr](https://www.data.gouv.fr) (jeux de données et API) et le catalogue
> [Melodi de l'INSEE](https://catalogue-donnees.insee.fr).
""")
        keywords_editor(show_queries=True)

        if st.button("🔎 Rechercher des données ouvertes", type="primary", disabled=not API_KEY):
            if ensure_keywords():
                queries = st.session_state.requetes_donnees or st.session_state.mots_cles[:5]
                with st.spinner("Interrogation de data.gouv.fr et de l'INSEE…"):
                    cands, errors = sources.opendata_candidates(queries, st.session_state.mots_cles)
                for e in errors:
                    st.warning(f"⚠️ Source inaccessible : {e}")

                def dsum(c):
                    return " | ".join(x for x in [
                        c["source"], c["type"], c["titre"], "producteur : " + c.get("producteur", ""),
                        c.get("description", "")[:200], "mise à jour : " + c.get("maj", ""),
                        ("période : " + c["periode"]) if c.get("periode") else "",
                    ] if x)

                extra = ""
                if kpis:
                    extra = (" Indicateurs de succès visés par l'expert : " + "; ".join(kpis)
                             + ". Dans 'comment_mobiliser', précise quel indicateur ou quel état des lieux "
                               "la donnée permet de calculer.")
                sel, synth = rank_with_claude(cands, "jeux de données et API ouverts", dsum,
                                              "jusqu'à 8", extra=extra)
                st.session_state.data_results = sel
                st.session_state.data_synthese = synth
                if not sel and not errors:
                    st.warning("Aucune donnée pertinente trouvée. Essayez d'ajuster les requêtes.")

        sel = st.session_state.data_results
        if sel:
            st.divider()
            if st.session_state.data_synthese:
                st.success(f"💡 {st.session_state.data_synthese}")
            st.subheader(f"📊 {len(sel)} source(s) de données")
            for item in sel:
                show_item(item, item.get("source", "Données"), [
                    f"{item.get('source', '')} · {item.get('type', '')}",
                    f"Producteur : {item.get('producteur', '')}" if item.get("producteur") else "",
                    f"Période : {item['periode']}" if item.get("periode") else "",
                    f"Mise à jour : {item.get('maj', '')}" if item.get("maj") else "",
                    f"Formats : {item['formats']}" if item.get("formats") else "",
                ])
            st.button("✅ Continuer vers les financements →", type="primary", on_click=next_phase)
        else:
            st.button("Passer cette étape →", on_click=next_phase)


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 10 — FINANCEMENTS (Aides-territoires + Mission Transition Écologique)
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == 10:
    phase_header("11", "Financements",
                 "Les aides publiques ouvertes qui peuvent financer votre projet.")

    if require_problem():
        st.markdown("""
> [Aides-territoires](https://aides-territoires.beta.gouv.fr) recense près de 3 000 aides publiques
> (État, ADEME, Régions, Départements, agences de l'eau, fonds européens…), surtout pour les
> collectivités. [Mission Transition Écologique](https://mission-transition-ecologique.beta.gouv.fr)
> complète avec environ 200 aides pour les entreprises.
""")
        if not sources.aides_territoires_key():
            st.warning("⚠️ Clé Aides-territoires absente : ajoutez `AIDES_TERRITOIRES_API_KEY` dans les "
                       "secrets Streamlit. Seules les aides Mission Transition Écologique seront cherchées.")
        keywords_editor()

        porteurs = list(sources.AT_AUDIENCES)
        c1, c2 = st.columns(2)
        with c1:
            porteur = st.selectbox(
                "Qui porte le projet ?", porteurs,
                index=porteurs.index(st.session_state.fin_porteur)
                if st.session_state.fin_porteur in porteurs else 0,
            )
            st.session_state.fin_porteur = porteur
        with c2:
            territoire = st.text_input(
                "Territoire (facultatif) : département, région ou numéro",
                value=st.session_state.fin_territoire,
                placeholder="Ex : Seine-et-Marne, Occitanie, 77…",
            )
            st.session_state.fin_territoire = territoire
        st.caption("Les aides nationales sont toujours incluses ; le territoire ajoute les aides locales "
                   "qui le couvrent.")

        if st.button("🔎 Rechercher des financements", type="primary", disabled=not API_KEY):
            if ensure_keywords():
                perimeter = None
                if territoire.strip():
                    try:
                        perimeter = sources.at_find_perimeter(territoire)
                    except Exception as e:  # noqa: BLE001
                        st.warning(f"⚠️ Territoire non vérifié : {e}")
                    if perimeter:
                        st.caption(f"📍 Territoire retenu : {perimeter['name']} ({perimeter['scale']})")
                    elif sources.aides_territoires_key():
                        st.warning(f"Territoire « {territoire} » introuvable : recherche sur toute la France.")
                with st.spinner("Recherche des aides ouvertes…"):
                    cands, errors = sources.funding_candidates(
                        st.session_state.mots_cles, sources.AT_AUDIENCES[porteur], perimeter,
                        include_mte=porteur in ("Tous types de porteurs", "Entreprise"))
                for e in errors:
                    st.warning(f"⚠️ {e}")

                def fsum(c):
                    return " | ".join(x for x in [
                        c["source"], c["titre"], c.get("description", "")[:220],
                        "financeurs : " + ", ".join(c.get("financeurs", [])[:3]),
                        "nature : " + c.get("nature", ""),
                        ("territoire : " + c["territoire"]) if c.get("territoire") else "",
                        ("bénéficiaires : " + ", ".join(c["publics"][:4])) if c.get("publics") else "",
                        ("date limite : " + c["date_limite"]) if c.get("date_limite") else "",
                    ] if x)

                extra = (f" Le porteur du projet est : {porteur}. Écarte les aides auxquelles il n'est "
                         "pas éligible. Dans 'comment_mobiliser', indique quelle partie du projet l'aide "
                         "peut financer (étude, investissement, animation…).")
                sel, synth = rank_with_claude(cands, "aides financières", fsum, "jusqu'à 10",
                                              extra=extra)
                st.session_state.fin_results = sel
                st.session_state.fin_synthese = synth
                if not sel and cands:
                    st.warning("Aucune aide jugée pertinente. Essayez d'élargir les mots-clés ou le porteur.")
                elif not cands and not errors:
                    st.warning("Aucune aide trouvée. Essayez d'autres mots-clés.")

        sel = st.session_state.fin_results
        if sel:
            st.divider()
            if st.session_state.fin_synthese:
                st.success(f"💡 {st.session_state.fin_synthese}")
            st.subheader(f"💶 {len(sel)} aide(s) pour votre projet")
            for item in sel:
                details = [
                    item.get("source", ""),
                    ("Financeur : " + ", ".join(item.get("financeurs", [])[:3])) if item.get("financeurs") else "",
                    item.get("nature", ""),
                    f"Taux : {item['taux']}" if item.get("taux") else "",
                    f"Territoire : {item['territoire']}" if item.get("territoire") else "",
                    f"⏰ Date limite : {item['date_limite']}" if item.get("date_limite") else
                    (item.get("recurrence") or ""),
                ]
                show_item(item, "Financements", details)
                if item.get("candidater") and item.get("candidater") != item.get("url"):
                    st.caption(f"↳ [Candidater / en savoir plus chez le financeur]({item['candidater']})")
            st.caption("Sources : Aides-territoires (Licence Ouverte 2.0) et Mission Transition Écologique, "
                       f"consultées le {datetime.now().strftime('%d/%m/%Y')}. Vérifiez toujours les "
                       "conditions et dates auprès du financeur.")
            st.button("✅ Continuer vers la synthèse →", type="primary", on_click=next_phase)
        else:
            st.button("Passer cette étape →", on_click=next_phase)


# ════════════════════════════════════════════════════════════════════════════════
# PHASE 11 — SYNTHÈSE & EXPORT
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == 11:
    phase_header("12", "Synthèse & Export",
                 "Votre problème, et tout ce qui existe déjà pour vous aider à le traiter.")

    if require_problem():
        retenus = list(st.session_state.retenus.values())
        if not retenus:
            st.warning("Vous n'avez retenu aucune ressource. Revenez aux phases 8 à 11 et cochez "
                       "« Retenir » sur celles qui vous intéressent.")
        else:
            groupes: dict[str, list] = {}
            for r in retenus:
                groupes.setdefault(r.get("origine", "Autre"), []).append(r)
            st.subheader(f"📌 {len(retenus)} ressource(s) retenue(s)")
            for origine, items in groupes.items():
                st.markdown(f"**{origine}**")
                for r in items:
                    lien = f"[{r.get('titre', '')}]({r['url']})" if r.get("url") else r.get("titre", "")
                    st.markdown(f"- {lien} — *{r.get('comment_mobiliser') or r.get('pourquoi', '')}*")

            if st.button("🧭 Générer la feuille de route de mobilisation", type="primary",
                         disabled=not API_KEY):
                listing = "\n".join(
                    f"- [{r.get('origine')}] {r.get('titre')} : {r.get('comment_mobiliser') or r.get('pourquoi', '')}"
                    for r in retenus)
                prompt = f"""{problem_brief()}

Ressources existantes retenues par l'expert :
{listing}

Propose une feuille de route pour s'appuyer sur ces ressources plutôt que de repartir de zéro.
Réponds UNIQUEMENT en JSON valide (aucun markdown) :
- "message_cle" : 1-2 phrases — ce que l'existant change dans la manière d'aborder le problème
- "actions" : 3 à 6 objets {{"action": "intitulé court", "ressources": "titres des ressources mobilisées", "detail": "1-2 phrases", "echeance": "ex : Mois 1"}}
- "a_construire" : 1-3 phrases — ce qui reste à construire car rien n'existe (la vraie valeur ajoutée du projet)"""
                with st.spinner("Rédaction de la feuille de route…"):
                    data = parse_json(claude(prompt, max_tokens=2000))
                if data:
                    st.session_state.feuille_route = data

            fr_ = st.session_state.feuille_route
            if fr_:
                st.divider()
                st.subheader("🧭 Feuille de route")
                if fr_.get("message_cle"):
                    st.info(fr_["message_cle"])
                for i, a in enumerate(fr_.get("actions", []), 1):
                    if isinstance(a, dict):
                        st.markdown(f"**{i}. {a.get('action', '')}** — ⏱ `{a.get('echeance', '')}`")
                        st.caption(f"{a.get('detail', '')}  \n📎 {a.get('ressources', '')}")
                if fr_.get("a_construire"):
                    st.success(f"🏗️ **Ce qui reste à construire** : {fr_['a_construire']}")

        # ── Export Word ──
        st.divider()
        st.subheader("📥 Exporter la fiche enrichie")
        if st.button("📄 Générer la fiche Word (.docx)", use_container_width=True):
            try:
                from docx import Document as Doc
                fd = st.session_state.final_data or {}
                doc = Doc()
                doc.add_heading("Fiche Problème enrichie", 0)
                doc.add_paragraph(f"Générée le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
                doc.add_heading("Le problème", level=1)
                if st.session_state.hmw:
                    doc.add_paragraph().add_run(st.session_state.hmw).bold = True
                if fd.get("formulation_complete"):
                    doc.add_paragraph(fd["formulation_complete"])
                if st.session_state.reformulation:
                    doc.add_paragraph(f"Problème général : {st.session_state.reformulation}")
                kp = [k for k in fd.get("indicateurs_succes", []) if isinstance(k, dict)]
                if kp:
                    doc.add_heading("Indicateurs de succès", level=1)
                    for k in kp:
                        doc.add_paragraph(f"{k.get('kpi', '')} : {k.get('cible', '')} {k.get('unite', '')} "
                                          f"— {k.get('echeance', '')}", style="List Bullet")
                for titre_s, synth in [("Communs & ressources (wiki FabMob)", st.session_state.wiki_synthese),
                                       ("Solutions France Mobilités", st.session_state.fm_synthese),
                                       ("Données ouvertes", st.session_state.data_synthese),
                                       ("Financements", st.session_state.fin_synthese)]:
                    if synth:
                        doc.add_heading(titre_s, level=2)
                        doc.add_paragraph(synth)
                if st.session_state.retenus:
                    doc.add_heading("Ressources retenues", level=1)
                    for r in st.session_state.retenus.values():
                        p = doc.add_paragraph(style="List Bullet")
                        p.add_run(f"[{r.get('origine', '')}] {r.get('titre', '')}").bold = True
                        txt = r.get("comment_mobiliser") or r.get("pourquoi") or ""
                        p.add_run(f" — {txt}\n{r.get('url', '')}")
                fr_ = st.session_state.feuille_route
                if fr_:
                    doc.add_heading("Feuille de route de mobilisation", level=1)
                    if fr_.get("message_cle"):
                        doc.add_paragraph(fr_["message_cle"])
                    for a in fr_.get("actions", []):
                        if isinstance(a, dict):
                            p = doc.add_paragraph(style="List Number")
                            p.add_run(a.get("action", "")).bold = True
                            p.add_run(f" ({a.get('echeance', '')}) — {a.get('detail', '')} "
                                      f"Ressources : {a.get('ressources', '')}")
                    if fr_.get("a_construire"):
                        doc.add_heading("Ce qui reste à construire", level=2)
                        doc.add_paragraph(fr_["a_construire"])
                buf = io.BytesIO()
                doc.save(buf)
                st.download_button(
                    "⬇️ Télécharger la fiche Word", data=buf.getvalue(),
                    file_name=f"fiche_probleme_enrichie_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
            except Exception as e:  # noqa: BLE001
                st.error(f"Erreur génération DOCX : {e}")


# ════════════════════════════════════════════════════════════════════════════════
# PIED DE PAGE COMMUN — navigation + sauvegarde (affiché à chaque phase)
# ════════════════════════════════════════════════════════════════════════════════
# Balise canonical vers France Mobilités sur les pages qui affichent leurs solutions
_fm_shown = (
    (st.session_state.phase == 8 and st.session_state.fm_results)
    or (st.session_state.phase == 11
        and any(r.get("origine") == "France Mobilités" for r in st.session_state.retenus.values()))
)
set_canonical(sources.FM_SOLUTIONS_PAGE if _fm_shown else None)

st.divider()
_cur = st.session_state.phase
f1, f2, f3 = st.columns([1, 1, 2])
with f1:
    st.button("◀ Étape précédente", disabled=_cur == 0, use_container_width=True,
              on_click=set_phase, args=(_cur - 1,), key="back_footer")
with f2:
    if _cur < st.session_state.max_phase:
        st.button("Étape suivante ▶", use_container_width=True,
                  on_click=set_phase, args=(_cur + 1,), key="next_footer",
                  help="Revenir à une étape déjà réalisée (vos résultats sont conservés).")
with f3:
    st.download_button(
        "💾 Sauvegarder ma progression",
        data=build_save(), file_name=save_filename(), mime="application/json",
        use_container_width=True, key="save_footer",
    )

sidebar_save_slot.download_button(
    "💾 Sauvegarder ma progression",
    data=build_save(), file_name=save_filename(), mime="application/json",
    use_container_width=True, key="save_sidebar",
)
