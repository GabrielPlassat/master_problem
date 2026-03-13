import streamlit as st
import requests
import json

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="L'Art de Problématiser",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .zoom-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 12px;
    }
    .zoom-global { background: #e8f4fd; color: #1a5276; border: 1px solid #aed6f1; }
    .zoom-local  { background: #eafaf1; color: #1e8449; border: 1px solid #a9dfbf; }
    .zoom-retour { background: #fef9e7; color: #9a7d0a; border: 1px solid #f9e79f; }
    .step-title  { font-size: 1.8rem; font-weight: 700; margin-bottom: 0; }
    .ref-link    { font-size: 0.85rem; }
    .portrait-box {
        background: #f8f9fa;
        border-left: 4px solid #2c3e50;
        padding: 20px 24px;
        border-radius: 4px;
        margin: 16px 0;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if 'step' not in st.session_state:
    st.session_state.step = 0
if 'answers' not in st.session_state:
    st.session_state.answers = {}

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

STEPS = [
    "Accueil",
    "Le Système Producteur",
    "Cartographie des Acteurs",
    "Les 5 Pourquoi Systémiques",
    "Positionnement Cynefin",
    "Carte des Tensions",
    "Test du Fantôme",
    "Évaluation du Problème",
    "Portrait du Problème",
]

ZOOM_TYPES = {
    "global":  ("🌍", "Vue globale — dézoomer", "zoom-global"),
    "local":   ("🔍", "Zoom avant — descendre dans le détail", "zoom-local"),
    "retour":  ("🔄", "Aller-retour — osciller entre les niveaux", "zoom-retour"),
}


def zoom_badge(zoom_type: str):
    icon, label, css = ZOOM_TYPES[zoom_type]
    st.markdown(
        f'<span class="zoom-badge {css}">{icon} {label}</span>',
        unsafe_allow_html=True,
    )


def nav_buttons():
    step = st.session_state.step
    max_step = len(STEPS) - 1
    col_back, _, col_next = st.columns([1, 4, 1])
    with col_back:
        if step > 0 and st.button("← Retour", use_container_width=True):
            st.session_state.step -= 1
            st.rerun()
    with col_next:
        if step < max_step and st.button("Suivant →", use_container_width=True, type="primary"):
            st.session_state.step += 1
            st.rerun()


def ref_box(refs: list[str]):
    with st.expander("📚 Pour aller plus loin — Références bibliographiques"):
        for r in refs:
            st.markdown(f"- {r}", unsafe_allow_html=True)


def example_box(eco: str, other: str):
    with st.expander("💡 Exemples concrets"):
        st.markdown("**🌿 Dans la transition écologique :**")
        st.info(eco)
        st.markdown("**🏙️ Dans un autre domaine :**")
        st.success(other)


def a(key, default=""):
    """Shortcut to get answer."""
    return st.session_state.answers.get(key, default)


def save(key, val):
    st.session_state.answers[key] = val


# ─────────────────────────────────────────────
# PROGRESS BAR
# ─────────────────────────────────────────────
step = st.session_state.step
progress = step / (len(STEPS) - 1)
st.progress(progress)
st.caption(f"Étape {step + 1} / {len(STEPS)}  ·  *{STEPS[step]}*")
st.markdown("---")


# ═══════════════════════════════════════════════════════════
# ÉTAPE 0 — ACCUEIL
# ═══════════════════════════════════════════════════════════
if step == 0:
    st.markdown("# 🎯 L'Art de Problématiser")
    st.markdown("### Un outil pour mieux poser son problème avant de chercher des solutions")

    st.markdown("""
> *"Tombez amoureux du problème, pas de la solution."*  
> — **Marty Cagan**, *Inspired* (2018)
""")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""**Ce que cet outil fait ✅**
- Vous aide à *habiter* votre problème
- Force les allers-retours global ↔ local
- Révèle les circularités et tensions cachées
- Produit un "Portrait du Problème" structuré""")
    with col2:
        st.markdown("""**Ce que cet outil ne fait pas ❌**
- Il ne propose aucune solution
- Il ne valide pas vos hypothèses
- Il ne remplace pas le terrain
- Il ne garantit pas d'avoir raison""")
    with col3:
        st.markdown("""**Durée estimée ⏱️**
- ~30 à 60 minutes
- 8 étapes progressives
- Un portrait synthétique final
- À compléter seul ou en équipe""")

    st.markdown("---")
    st.markdown("### Pour commencer, décrivez brièvement votre problème")

    prob = st.text_area(
        "En quelques phrases, quel est le problème que vous voulez explorer ?",
        value=a("problem_initial"),
        height=120,
        placeholder="Ex : Les agriculteurs de la région utilisent trop de pesticides malgré la réglementation et les formations disponibles...",
    )
    save("problem_initial", prob)

    domain = st.text_input(
        "Dans quel domaine / secteur se situe ce problème ?",
        value=a("domain"),
        placeholder="Ex : Agriculture, Mobilité, Énergie, Alimentation, Eau...",
    )
    save("domain", domain)

    ref_box([
        "[**Marty Cagan** — *Inspired: How to Create Tech Products Customers Love* (2018)](https://www.svpg.com/books/inspired-how-to-create-tech-products-customers-love-2nd-edition/) : la bible du développement de produit centré sur le problème.",
        "[**Donella Meadows** — *Thinking in Systems: A Primer* (2008)](https://www.chelseagreen.com/product/thinking-in-systems/) : introduction fondamentale à la pensée systémique.",
        "[**The Systems Thinker** — Ressource en ligne sur les outils de pensée systémique](https://thesystemsthinker.com/) : articles, archétypes, outils.",
    ])

    nav_buttons()


# ═══════════════════════════════════════════════════════════
# ÉTAPE 1 — LE SYSTÈME PRODUCTEUR
# ═══════════════════════════════════════════════════════════
elif step == 1:
    zoom_badge("global")
    st.markdown("## 🌍 Le Système Producteur")

    st.markdown("""
### La question fondatrice

> *"Ce problème existe parce qu'un système fonctionne **parfaitement** — lequel ?"*

Cette question renverse notre regard habituel. Les problèmes persistants ne sont pas des 
dysfonctionnements : ils sont **les produits cohérents d'un système qui fonctionne exactement 
comme il a été conçu**.

Identifier ce système, c'est déjà comprendre pourquoi les solutions superficielles échouent — 
et pourquoi elles seront réabsorbées par le système.
""")

    st.markdown("---")

    sysname = st.text_area(
        "Quel système produit votre problème ? Nommez-le.",
        value=a("system_name"),
        height=80,
        placeholder="Ex : Le système agro-industriel fondé sur la dette des exploitations et la maximisation des rendements à court terme...",
    )
    save("system_name", sysname)

    st.markdown("#### Décrivez la boucle circulaire qui maintient le problème en place")
    st.caption(
        "Une boucle circulaire : A produit B → B renforce C → C renforce A. "
        "Le problème est au cœur de cette boucle, pas à son origine."
    )

    loop = st.text_area(
        "Décrivez les étapes de la boucle (utilisez des flèches →)",
        value=a("circular_loop"),
        height=120,
        placeholder="Ex : Endettement agricole → besoin de rendements élevés → usage de pesticides → sol appauvri → dépendance aux intrants → plus d'endettement → ...",
    )
    save("circular_loop", loop)

    benefits = st.text_area(
        "Qui bénéficie (directement ou indirectement) de ce système tel qu'il est ?",
        value=a("who_benefits"),
        height=80,
        placeholder="Ex : Firmes agrochimiques, banques agricoles, grande distribution qui achète au prix le plus bas...",
    )
    save("who_benefits", benefits)

    example_box(
        """**Problème : "Les agriculteurs utilisent trop de pesticides"**

🔁 **La boucle circulaire :**
Les prix agricoles baissent → les agriculteurs s'endettent pour maintenir leurs revenus → ils doivent maximiser les rendements → ils utilisent plus d'intrants chimiques → les sols s'appauvrissent → les rendements naturels baissent → ils ont besoin de encore plus d'intrants → la surproduction fait encore baisser les prix...

🟢 **Qui en bénéficie ?** Les firmes agrochimiques (volume de vente), les banques (intérêts sur les dettes), la grande distribution (prix d'achat bas), les consommateurs à court terme (prix bas en rayon).

Ce système *fonctionne parfaitement* — pour certains acteurs, pendant un certain temps.""",
        """**Problème : "Les urgences hospitalières sont saturées"**

🔁 **La boucle circulaire :**
Manque de médecins généralistes → les patients vont aux urgences pour des cas non-urgents → les urgences se saturent → les délais explosent → les médecins urgentistes s'épuisent et quittent → encore moins de capacité → encore plus de saturation...

🟢 **Qui en bénéficie ?** Les cliniques privées qui récupèrent les patients solvables, les assurances complémentaires qui valorisent leur couverture, certains acteurs de l'urgence privée.""",
    )

    ref_box([
        "[**Donella Meadows** — *Thinking in Systems* (2008)](https://www.chelseagreen.com/product/thinking-in-systems/) : les boucles de rétroaction (renforçantes et compensatrices) et les archétypes systémiques.",
        "[**Peter Senge** — *La Cinquième Discipline* (1990)](https://en.wikipedia.org/wiki/The_Fifth_Discipline) : les 11 lois de la systémique, dont 'La cause et l'effet ne sont pas proches dans le temps et l'espace'.",
        "[**Systems Archetypes Basics** — The Systems Thinker](https://thesystemsthinker.com/systems-archetypes-basics-from-story-to-structure/) : visualiser les boucles classiques (escalade, dépendance, fixes qui échouent).",
        "[**W. Brian Arthur** — *The Nature of Technology* (2009)](https://www.penguinrandomhouse.com/books/28462/the-nature-of-technology-by-w-brian-arthur/) : pourquoi les systèmes technologiques et institutionnels se verrouillent.",
    ])

    nav_buttons()


# ═══════════════════════════════════════════════════════════
# ÉTAPE 2 — CARTOGRAPHIE DES ACTEURS
# ═══════════════════════════════════════════════════════════
elif step == 2:
    zoom_badge("local")
    st.markdown("## 🔍 Cartographie des Acteurs")

    st.markdown("""
### Qui souffre ? Qui agit ? Qui décide ? Qui est invisible ?

La cartographie des acteurs est un **zoom sur les humains concrets** impliqués dans le problème.
Elle évite le piège du problème abstrait ("le système alimentaire") et force à nommer des 
personnes réelles avec des besoins réels, des intérêts réels — et parfois des intérêts contradictoires.

> *"Un problème bien défini est toujours ancré dans une expérience humaine spécifique."*  
> — **Marius Ursache**, *The Problem Statement Canvas*
""")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🔴 Ceux qui souffrent")
        suf = st.text_area(
            "Qui vit le problème au quotidien ? Soyez précis — pas 'les agriculteurs' mais 'les éleveurs laitiers de moins de 80 vaches en zone de montagne'.",
            value=a("sufferers"), height=100,
        )
        save("sufferers", suf)

        st.markdown("#### 🟡 Ceux qui décident")
        dec = st.text_area(
            "Qui a le pouvoir de changer les règles du jeu ? Qui fixe les normes, les budgets, les politiques ?",
            value=a("deciders"), height=100,
        )
        save("deciders", dec)

    with col2:
        st.markdown("#### 🟢 Ceux qui bénéficient du statu quo")
        ben = st.text_area(
            "Qui a intérêt à ce que rien ne change ? Même implicitement, même sans le revendiquer.",
            value=a("beneficiaries"), height=100,
        )
        save("beneficiaries", ben)

        st.markdown("#### ⚪ Les invisibles")
        inv = st.text_area(
            "Qui est affecté mais n'a pas voix au chapitre ? (générations futures, non-humains, acteurs lointains, personnes sans représentation...)",
            value=a("invisible"), height=100,
        )
        save("invisible", inv)

    st.markdown("---")
    st.markdown("#### 🎯 Le client du problème")
    st.caption("Pour qui ce problème doit-il être résolu **en priorité** ? Cette discipline de choix est essentielle.")
    primary = st.text_area(
        "Une seule réponse possible — une catégorie de personne concrète.",
        value=a("primary_actor"), height=60,
        placeholder="Ex : Les petits maraîchers en circuits courts qui ne peuvent pas absorber le coût d'une transition sans accompagnement...",
    )
    save("primary_actor", primary)

    example_box(
        """**Problème : Déclin de la biodiversité dans les zones agricoles intensives**

🔴 **Souffrent** : Les apiculteurs (mortalité des ruches), les agriculteurs bio voisins (dérive phytosanitaire), les pêcheurs (pollution des nappes), les générations futures
🟡 **Décident** : Ministères Agriculture et Environnement, syndicats agricoles majoritaires (FNSEA), instances européennes (PAC)
🟢 **Bénéficient du statu quo** : Firmes agrochimiques (Bayer, BASF), coopératives d'intrants, banques (financement des équipements), filières d'exportation céréalières
⚪ **Invisibles** : Les insectes eux-mêmes, les sols vivants, les rivières, les agricultrices (sous-représentées dans les instances de décision)

🎯 **Client prioritaire** : Les agriculteurs en transition qui font face à une période de vulnérabilité économique et technique sans filet de sécurité.""",
        """**Problème : Fracture numérique chez les seniors en zone rurale**

🔴 **Souffrent** : Les seniors isolés, leurs aidants familiaux, les agents de services publics dématérialisés en première ligne
🟡 **Décident** : Opérateurs télécom, État (plan France Numérique), collectivités
🟢 **Bénéficient du statu quo** : Acteurs de l'aide à domicile "physique", certaines mutuelles et banques (maintien des agences comme différenciation)
⚪ **Invisibles** : Les aidants familiaux épuisés, les personnes en EHPAD, les personnes handicapées""",
    )

    ref_box([
        "[**Marius Ursache** — *The Problem Statement Canvas* (Medium)](https://medium.com/@marius.ursache/the-problem-statement-canvas-fd21c7d89b0e) : décomposer le problème sans solution.",
        "[**Tony Ulwick** — *Jobs-to-be-Done: Theory to Practice* (2016), Strategyn](https://strategyn.com/jobs-to-be-done/) : identifier les véritables besoins fonctionnels, émotionnels, sociaux.",
        "[**Stakeholder Mapping** — Interaction Design Foundation](https://www.interaction-design.org/literature/topics/stakeholder-mapping) : méthode complète de cartographie.",
        "[**Bruno Latour** — *Nous n'avons jamais été modernes* (1991)](https://www.editionsladecouverte.fr/nous_n_avons_jamais_ete_modernes-9782707182500) : pourquoi inclure les acteurs non-humains dans l'analyse.",
    ])

    nav_buttons()


# ═══════════════════════════════════════════════════════════
# ÉTAPE 3 — LES 5 POURQUOI SYSTÉMIQUES
# ═══════════════════════════════════════════════════════════
elif step == 3:
    zoom_badge("retour")
    st.markdown("## 🔄 Les 5 Pourquoi Systémiques")

    st.markdown("""
### Remonter des symptômes aux structures

La technique des **5 Pourquoi** (Taiichi Ohno, Toyota) consiste à questionner chaque 
réponse jusqu'à atteindre la cause racine. Ici on y ajoute une couche systémique : 
à chaque niveau, on identifie si la cause est :

| Type | Définition | Exemple |
|------|-----------|---------|
| 📊 **Flux** | Quelque chose qui circule : argent, information, énergie, personnes | Le crédit bancaire qui finance les intrants |
| 🏗️ **Structure** | Une organisation physique ou institutionnelle | La coopérative qui impose les intrants |
| 📜 **Règle / Paradigme** | Une norme, une loi, une croyance, un modèle mental | "L'agriculture intensive est la seule rentable" |

> *"Les leviers d'action les plus puissants dans un système ne sont pas les flux, 
> ni même les structures, mais les règles et les paradigmes."*  
> — **Donella Meadows**, *Places to Intervene in a System* (1999)
""")

    st.markdown("---")
    prob_display = a("problem_initial") or "votre problème"
    st.info(f"**Problème de départ :** *{prob_display}*")
    st.markdown("---")

    type_options = ["📊 Flux", "🏗️ Structure", "📜 Règle / Paradigme"]

    for i in range(1, 6):
        col1, col2 = st.columns([3, 1])
        with col1:
            label = "Quelle est la cause du problème initial ?" if i == 1 else f"Pourquoi est-ce ainsi ? (cause #{i})"
            ans = st.text_area(
                label,
                value=a(f"why_{i}"),
                height=65,
                key=f"why_{i}_input",
                placeholder="Expliquez la cause...",
            )
            save(f"why_{i}", ans)
        with col2:
            default_idx = type_options.index(a(f"why_type_{i}")) if a(f"why_type_{i}") in type_options else 0
            wtype = st.selectbox("Type", type_options, key=f"why_type_{i}_sel", index=default_idx)
            save(f"why_type_{i}", wtype)

    st.markdown("---")
    root = st.text_area(
        "🎯 **Cause racine identifiée** : en une phrase, quelle est la véritable cause fondamentale ?",
        value=a("root_cause"), height=80,
        placeholder="Ex : Un verrouillage institutionnel où ceux qui bénéficient du modèle intensif contrôlent les règles du financement agricole.",
    )
    save("root_cause", root)

    example_box(
        """**Problème : "Les agriculteurs n'adoptent pas les pratiques agroécologiques"**

Cause #1 : C'est financièrement risqué pendant la période de transition → **📊 Flux** (revenus)
Cause #2 : Les aides PAC récompensent le volume produit, pas les pratiques → **📜 Règle**
Cause #3 : La PAC a été conçue pour garantir la sécurité alimentaire post-guerre → **📜 Paradigme**
Cause #4 : Ce paradigme n'a jamais été fondamentalement remis en question malgré les crises → **🏗️ Structure** (institutions agricoles)
Cause #5 : Les institutions agricoles sont dominées par les acteurs du modèle intensif → **🏗️ Structure** (pouvoir)

**Cause racine :** Un verrouillage institutionnel où ceux qui bénéficient du système actuel contrôlent les règles du jeu — et donc les incitations.""",
        """**Problème : "Les jeunes diplômés quittent les territoires ruraux"**

Cause #1 : Il n'y a pas d'emplois correspondant à leurs qualifications → **📊 Flux** (emploi)
Cause #2 : Les entreprises s'installent en métropoles → **🏗️ Structure**
Cause #3 : Les métropoles concentrent infrastructures et capital humain → **📊 Flux**
Cause #4 : Les investissements publics sont historiquement centralisés → **📜 Règle**
Cause #5 : Le modèle de développement dominant valorise la concentration → **📜 Paradigme**

**Cause racine :** Un paradigme du développement qui assimile croissance et concentration géographique.""",
    )

    ref_box([
        "[**Taiichi Ohno** — Origine des 5 Pourquoi, *Toyota Production System* (1978)](https://en.wikipedia.org/wiki/Five_whys) : la méthode originale appliquée à la résolution de problèmes industriels.",
        "[**Donella Meadows** — *Places to Intervene in a System* (1999)](https://donellameadows.org/archives/leverage-points-places-to-intervene-in-a-system/) : les 12 points de levier, du moins au plus puissant — à lire absolument.",
        "[**The Iceberg Model** — Academy for Systems Change](https://www.academyforchange.org/the-iceberg-model/) : événements, comportements, structures, modèles mentaux.",
        "[**Peter Senge** — *La Cinquième Discipline* (1990)](https://en.wikipedia.org/wiki/The_Fifth_Discipline) : distinguer les boucles d'événements, de comportements et de structures.",
    ])

    nav_buttons()


# ═══════════════════════════════════════════════════════════
# ÉTAPE 4 — CYNEFIN
# ═══════════════════════════════════════════════════════════
elif step == 4:
    zoom_badge("global")
    st.markdown("## 🌐 Positionner votre Problème — Cadre Cynefin")

    st.markdown("""
### Dans quel type d'environnement votre problème existe-t-il ?

Le **cadre Cynefin** (Dave Snowden, 1999) est un outil de *sense-making* qui permet 
d'adapter votre méthode au type de complexité réelle du problème. 

> **Erreur fréquente** : traiter un problème complexe avec des outils du monde compliqué 
> (analyses, plans d'action) — cela mène inévitablement à l'échec ou à la régression.
""")

    col1, col2 = st.columns(2)
    with col1:
        st.info("""**🟦 Clair / Évident**
Cause → Effet connu et répétable.  
Approche : *Identifier → Catégoriser → Appliquer les meilleures pratiques.*  
Ex : Calculer l'empreinte carbone d'un produit selon un standard reconnu.""")
        st.warning("""**🟨 Complexe**
Cause ↔ Effet imprévisible, émergent. On ne comprend qu'en agissant.  
Approche : *Sonder → Observer → Adapter.*  
Ex : Changer les comportements alimentaires d'une région entière.""")
    with col2:
        st.success("""**🟩 Compliqué**
Plusieurs bonnes réponses, expertise requise.  
Approche : *Analyser → Consulter les experts → Recommander.*  
Ex : Optimiser un réseau de chaleur urbain avec des contraintes techniques.""")
        st.error("""**🟥 Pernicieux (Wicked Problem)**
Pas de définition définitive possible. Le problème est lui-même contesté.  
Approche : *Recadrer → Co-construire → Expérimenter avec prudence.*  
Ex : Inégalités environnementales, artificialisation des sols, transition juste.""")

    st.markdown("---")

    cynefin_options = [
        "🟦 Clair — les relations de cause à effet sont connues et répétables",
        "🟩 Compliqué — plusieurs bonnes réponses existent, l'expertise est nécessaire",
        "🟨 Complexe — causes et effets ne sont compréhensibles qu'a posteriori",
        "🟥 Pernicieux — le problème lui-même est contesté, sans formulation définitive",
    ]
    default_cyn = a("cynefin") if a("cynefin") in cynefin_options else cynefin_options[2]
    cyn = st.radio("Où situez-vous votre problème ?", cynefin_options,
                   index=cynefin_options.index(default_cyn))
    save("cynefin", cyn)

    cyn_just = st.text_area(
        "Pourquoi ce positionnement ? (2-3 éléments concrets qui justifient votre choix)",
        value=a("cynefin_justification"), height=80,
    )
    save("cynefin_justification", cyn_just)

    # Implication dynamique
    st.markdown("#### 💡 Implication pour votre démarche")
    if "Clair" in cyn:
        st.info("Les solutions existent probablement déjà. Cherchez les meilleures pratiques existantes. ⚠️ *Attention : êtes-vous sûr de ne pas simplifier à l'excès un problème plus complexe ?*")
    elif "Compliqué" in cyn:
        st.success("Réunissez des expertises variées et interdisciplinaires. La solution optimale existe mais nécessite de l'analyse approfondie. ⚠️ *Attention au biais d'expert et à la confiance excessive dans les modèles.*")
    elif "Complexe" in cyn:
        st.warning("Privilégiez les petites expérimentations rapides et sûres à échouer. N'attendez pas de tout comprendre avant d'agir. Favorisez la diversité des approches en parallèle. ⚠️ *Attention : une solution qui fonctionne ici peut échouer ailleurs.*")
    else:
        st.error("Il faut d'abord stabiliser la définition du problème *avec* les parties prenantes. Le recadrage (Kees Dorst) et la co-construction sont essentiels. ⚠️ *Méfiez-vous de toute solution présentée comme évidente — elle sera au service d'un acteur particulier.*")

    example_box(
        """**Transition vers l'agroécologie** → 🟥 Pernicieux

Pourquoi pernicieux ? "L'agroécologie" est elle-même un terme contesté politiquement. Certains acteurs y incluent le bio industriel, d'autres exigent l'autonomie paysanne et la souveraineté semencière. Le problème est redéfini par chaque acteur selon ses intérêts. Il est impossible de le résoudre sans d'abord travailler sur sa définition partagée.

**Réduction du gaspillage alimentaire en restauration scolaire** → 🟩 Compliqué

Pourquoi compliqué ? Les causes sont identifiables (surstockage, menus inadaptés, absence de pesée des déchets, horaires de repas trop courts). Les solutions existent et ont fait leurs preuves ailleurs. Il s'agit d'analyser le contexte précis et d'adapter les bonnes pratiques.""",
        """**Addiction aux écrans chez les adolescents** → 🟥 Pernicieux
(Le problème est contesté dans sa définition même : addiction ? Rapport pathologique ? Symptôme d'autre chose ?)

**Congestion routière dans une métropole** → 🟨 Complexe
(Les comportements de mobilité émergent de milliers de décisions individuelles imprévisibles)

**Optimisation de la logistique d'un entrepôt** → 🟩 Compliqué
(Expertise requise, solution optimale identifiable par l'analyse)""",
    )

    ref_box([
        "[**Dave Snowden** — Introduction au cadre Cynefin (vidéo originale, 2010)](https://www.youtube.com/watch?v=N7oz366X0-8) : 18 minutes indispensables.",
        "[**Andy Cleff** — *Navigating Complexity aka Cynefin for Dummies* (2017, Medium)](https://medium.com/@andycleff/navigating-complexity-aka-cynefin-for-dummies-7a7a9f4e5e8) : synthèse accessible.",
        "[**Rittel & Webber** — *Dilemmas in a General Theory of Planning* (1973)](https://www.cc.gatech.edu/fac/ellendo/rittel/rittel-dilemma.pdf) : l'article fondateur sur les Wicked Problems.",
        "[**Lesne, André, Simos** — *Complexe / Compliqué / Pernicieux*, Revue ERS (2018)](https://www.jle.com/fr/revues/ers/e-docs/complexe_complique_pernicieux_311879/article.phtml) : distinction rigoureuse des trois régimes.",
    ])

    nav_buttons()


# ═══════════════════════════════════════════════════════════
# ÉTAPE 5 — CARTE DES TENSIONS
# ═══════════════════════════════════════════════════════════
elif step == 5:
    zoom_badge("retour")
    st.markdown("## ⚡ Carte des Tensions")

    st.markdown("""
### Les paradoxes qui font tenir le problème en place

Les problèmes persistants, en particulier dans la transition écologique, ne sont pas 
des problèmes techniques mal résolus. Ils sont des **nœuds de tensions** entre des valeurs, 
des temporalités ou des légitimités contradictoires.

Nommer ces tensions explicitement, c'est déjà comprendre pourquoi les solutions habituelles 
sont soit rejetées, soit réabsorbées.

> *"Il n'y a pas de solution à un paradoxe. Il y a une façon de le tenir."*  
> — **Kees Dorst**, *Frame Innovation* (2015)
""")

    st.markdown("---")
    st.markdown("#### Identifiez jusqu'à 3 tensions constitutives de votre problème")

    nature_options = [
        "Vraie contradiction — les deux ne peuvent coexister dans le système actuel",
        "Fausse dichotomie — les deux sont peut-être compatibles si on recadre",
        "Tension créative — la friction elle-même peut être productive",
    ]

    for i in range(1, 4):
        st.markdown(f"**Tension {i}**")
        col1, mid, col2 = st.columns([5, 1, 5])
        with col1:
            ta = st.text_input("Valeur / logique A", value=a(f"t{i}_a"), key=f"t{i}_a_in",
                               placeholder="Ex : Urgence climatique")
            save(f"t{i}_a", ta)
        with mid:
            st.markdown("<br><br>**↔️**", unsafe_allow_html=True)
        with col2:
            tb = st.text_input("Valeur / logique B", value=a(f"t{i}_b"), key=f"t{i}_b_in",
                               placeholder="Ex : Temps démocratique")
            save(f"t{i}_b", tb)

        default_nat = a(f"t{i}_nature") if a(f"t{i}_nature") in nature_options else nature_options[0]
        nat = st.radio("Nature de cette tension :", nature_options,
                       key=f"t{i}_nat", horizontal=True,
                       index=nature_options.index(default_nat))
        save(f"t{i}_nature", nat)
        st.markdown("---")

    example_box(
        """**Problème : Développer les énergies renouvelables en zones rurales**

⚡ Tension 1 : **Souveraineté énergétique locale** ↔ **Rentabilité pour les investisseurs financiers** → *Vraie contradiction dans le modèle économique actuel*

⚡ Tension 2 : **Préservation des paysages et du patrimoine** ↔ **Décarbonation rapide** → *Fausse dichotomie : le design et la concertation peuvent réconcilier les deux*

⚡ Tension 3 : **Urgence climatique** ↔ **Temps de la concertation démocratique** → *Tension créative : une concertation bien menée accélère l'acceptabilité et donc le déploiement*""",
        """**Problème : Réforme du système éducatif**

⚡ Tension 1 : **Égalité des chances** ↔ **Excellence académique sélective** → *Fausse dichotomie : les systèmes finlandais ou canadiens montrent leur compatibilité*

⚡ Tension 2 : **Autonomie pédagogique des enseignants** ↔ **Standardisation nationale des programmes** → *Vraie contradiction dans le cadre réglementaire actuel*

⚡ Tension 3 : **Résultats à court terme (examens, classements)** ↔ **Apprentissage en profondeur** → *Tension créative : peut mener à repenser l'évaluation elle-même*""",
    )

    ref_box([
        "[**Kees Dorst** — *Frame Innovation: Create New Thinking by Design*, MIT Press (2015)](https://mitpress.mit.edu/9780262533843/frame-innovation/) : la méthode complète en 9 étapes pour les problèmes ouverts.",
        "[**Barry Johnson** — *Polarity Management: Identifying and Managing Unsolvable Problems* (1992)](https://www.polaritypartnerships.com/) : gérer les paradoxes plutôt que de prétendre les résoudre.",
        "[**Roger Martin** — *The Opposable Mind* (2007)](https://rogerlmartin.com/lets-read/the-opposable-mind) : la pensée intégrative, ou comment tenir deux idées contradictoires simultanément.",
        "[**oxd.com** — *How Frame Creation can inspire innovation*](https://www.oxd.com/about/the-oxd-press/articles/frame-creation-design) : présentation et cas d'application de la méthode Dorst.",
    ])

    nav_buttons()


# ═══════════════════════════════════════════════════════════
# ÉTAPE 6 — TEST DU FANTÔME
# ═══════════════════════════════════════════════════════════
elif step == 6:
    zoom_badge("retour")
    st.markdown("## 👻 Le Test du Fantôme")

    st.markdown("""
### Trois regards radicalement différents sur votre problème

Inspiré du **Frame Innovation** de Kees Dorst, le Test du Fantôme soumet votre 
problème à trois perspectives fictives mais rigoureuses.

**Objectif :** Révéler les angles morts de votre formulation actuelle.  
**Méthode :** Pour chaque fantôme, laissez-vous guider par sa logique propre pour 
reformuler le problème — même si cela vous met mal à l'aise. *Surtout* si cela vous met mal à l'aise.

> *"Le recadrage, c'est changer de métaphore pour changer de question."*  
> — **Kees Dorst**, *Frame Innovation*
""")

    st.info(f"**Votre problème de départ :** *{a('problem_initial') or 'non renseigné'}*")
    st.markdown("---")

    ghosts = [
        (
            "👧",
            "Un enfant de 10 ans en 2050",
            "Cet enfant subit les conséquences de ce que nous n'avons pas résolu aujourd'hui. Il ne comprend pas nos rationalisations économiques. Il voit les effets, pas les justifications. Comment reformule-t-il votre problème, sans pudeur ?",
        ),
        (
            "💰",
            "Un acteur économique qui bénéficie du statu quo",
            "Il a tout intérêt à ce que le problème reste non résolu ou mal formulé. Il n'est pas forcément malveillant — il défend sa position dans un système. Comment définit-il lui-même le problème pour neutraliser toute remise en cause ?",
        ),
        (
            "🌿",
            "Un écosystème non-humain (une rivière, un sol, une forêt)",
            "Il n'a pas de voix mais est pleinement affecté. Il mesure le problème en termes de flux, de cycles, de santé des systèmes vivants — pas d'indicateurs économiques. Comment formulerait-il le problème s'il pouvait parler ?",
        ),
    ]

    for icon, name, instruction in ghosts:
        st.markdown(f"#### {icon} Perspective : *{name}*")
        st.caption(instruction)
        ans = st.text_area(
            f"Comment *{name}* reformule-t-il le problème ?",
            value=a(f"ghost_{name}"),
            height=85,
            key=f"ghost_ta_{name}",
        )
        save(f"ghost_{name}", ans)
        st.markdown("---")

    ghost_names = [g[1] for g in ghosts]
    default_unc = a("most_uncomfortable") if a("most_uncomfortable") in ghost_names else ghost_names[0]
    unc = st.radio(
        "Quelle reformulation vous est la plus inconfortable ? (souvent la plus révélatrice)",
        ghost_names,
        index=ghost_names.index(default_unc),
    )
    save("most_uncomfortable", unc)

    insight = st.text_area(
        "Qu'est-ce que ce malaise révèle sur votre formulation initiale du problème ?",
        value=a("reframe_insight"), height=80,
    )
    save("reframe_insight", insight)

    example_box(
        """**Problème initial : "Les consommateurs ne choisissent pas les produits locaux et durables"**

👧 Enfant de 2050 : *"Pourquoi les adultes ont-ils laissé les supermarchés décider de ce qu'on mangeait ?"*
→ Reformulation : Le problème n'est pas le choix individuel du consommateur, c'est l'architecture de choix imposée par la distribution industrielle.

💰 Grande distribution : *"Le problème, c'est que les consommateurs manquent d'information et d'éducation alimentaire."*
→ Ce cadrage révèle : il déplace la responsabilité vers l'individu et protège le modèle commercial. C'est la formulation qu'on retrouve dans tous leurs rapports RSE.

🌿 Un sol agricole : *"Chaque produit ultra-transformé représente de l'énergie solaire, de l'eau, du vivant qui ne reviendra pas dans le cycle."*
→ Reformulation : Le problème est la déconnexion totale entre la valeur marchande et la valeur écologique réelle des aliments.""",
        """**Problème initial : "Les employés résistent au changement organisationnel"**

👧 Enfant de 2050 : *"Pourquoi les adultes passaient-ils autant de temps à se réorganiser plutôt qu'à travailler vraiment ?"*

💰 Cabinet de conseil : *"Le problème, c'est l'absence de conduite du changement structurée."*
→ Révèle : ce cadrage protège le marché du conseil et ignore les causes profondes (perte de sens, management défaillant).

🌿 L'organisation comme système vivant : *"On me demande de changer de forme sans comprendre comment je vis, comment je m'autorégule, comment je crée."*""",
    )

    ref_box([
        "[**Kees Dorst** — *Frame Innovation*, MIT Press (2015)](https://mitpress.mit.edu/9780262533843/frame-innovation/) : la méthode complète en 9 étapes pour les problèmes ouverts et complexes.",
        "[**oxd.com** — *Frame Creation case studies* : le cas Kings Cross à Sydney](https://www.oxd.com/about/the-oxd-press/articles/frame-creation-design) : comment une métaphore de 'festival de musique' a résolu un problème de criminalité nocturne.",
        "[**Edward de Bono** — *Six Thinking Hats* (1985)](https://www.edwarddebono.com/six-thinking-hats) : changer de perspective de manière structurée et collective.",
        "[**Bruno Latour & Peter Weibel** — *Making Things Public* (2005)](https://mitpress.mit.edu/9780262622028/making-things-public/) : donner voix aux non-humains et aux absents dans les assemblées.",
    ])

    nav_buttons()


# ═══════════════════════════════════════════════════════════
# ÉTAPE 7 — ÉVALUATION
# ═══════════════════════════════════════════════════════════
elif step == 7:
    zoom_badge("local")
    st.markdown("## 📊 Évaluation du Problème")

    st.markdown("""
### Les 5 critères d'un "bon" problème + 1 critère systémique

Cette grille est issue des travaux sur la **problématisation stratégique**.  
Évaluez votre problème tel qu'il est formulé *maintenant* — après les étapes précédentes.  
Soyez honnête : cette évaluation est un outil de travail, pas un jugement.
""")

    criteria = [
        (
            "🚀", "Impact & Échelle",
            "Le problème génère-t-il un impact transformateur suffisamment grand s'il est résolu ?",
            "Trop petit : 'réduire le papier dans nos bureaux.'  Suffisant : 'réduire de 30% les émissions de la filière textile régionale d'ici 5 ans.'"
        ),
        (
            "🔧", "Faisabilité",
            "Peut-on définir une première étape concrète et réalisable avec les ressources disponibles ?",
            "Trop vague : 'transformer le système alimentaire.' Actionnable : 'tester un circuit court avec 3 cantines scolaires d'ici la rentrée.'"
        ),
        (
            "💬", "Clarté & Engagement",
            "Le problème est-il formulé sans ambiguïté, de façon à susciter l'adhésion émotionnelle des parties prenantes ?",
            "Jargon : 'optimiser la chaîne de valeur agro-écologique.' Clair : 'comment aider les éleveurs à moins dépendre des intrants chimiques sans perdre de revenus ?'"
        ),
        (
            "🎯", "Précision & Apprentissage",
            "Le problème est-il assez délimité pour définir des indicateurs de succès clairs et tester des hypothèses ?",
            "Flou : 'améliorer la biodiversité.' Précis : 'augmenter le nombre d'espèces pollinisatrices dans les vergers de la région X d'ici 3 ans, mesuré par comptage annuel.'"
        ),
        (
            "🧭", "Alignement Stratégique",
            "Le problème s'inscrit-il dans une vision à long terme et les objectifs globaux de l'organisation ou du territoire ?",
            "Déconnecté : action isolée sans lien avec les engagements territoriaux. Aligné : ancré dans le PCAET, la stratégie de transition, les ODD."
        ),
        (
            "🔁", "Réversibilité *(critère systémique)*",
            "Si on se trompe sur ce problème, peut-on corriger le tir ? Les expériences proposées sont-elles sûres à échouer ?",
            "Irréversible : artificialiser des terres agricoles. Réversible : expérimenter des pratiques sur une parcelle pilote avec un suivi."
        ),
    ]

    scores = {}
    for icon, name, question, ex in criteria:
        st.markdown(f"#### {icon} {name}")
        st.caption(question)
        st.caption(f"💡 *{ex}*")
        default_score = a(f"score_{name}") if isinstance(a(f"score_{name}"), int) else 3
        score = st.slider(f"", 1, 5, value=default_score, key=f"slider_{name}", format="%d / 5")
        save(f"score_{name}", score)
        scores[name] = score
        st.markdown("---")

    total = sum(scores.values())
    max_total = len(criteria) * 5
    pct = total / max_total * 100

    col_s, col_b = st.columns([1, 3])
    with col_s:
        st.metric("Score global", f"{total} / {max_total}", f"{pct:.0f}%")
    with col_b:
        if pct >= 80:
            st.success("✅ **Votre problème est bien formulé.** Vous êtes prêt à passer à la phase exploratoire — confrontez-le au terrain.")
        elif pct >= 60:
            st.warning("⚠️ **Votre problème est en bonne voie** mais mérite d'être affiné sur les critères les plus faibles avant d'aller plus loin.")
        else:
            st.error("🔄 **Votre problème nécessite encore du travail.** Revenez aux étapes précédentes pour approfondir — c'est normal à ce stade.")

    weakest = min(scores, key=scores.get)
    st.info(f"💡 **Point à renforcer en priorité :** *{weakest}* (score actuel : {scores[weakest]}/5)")

    ref_box([
        "[**L'Ingénierie de la Problématisation Stratégique** — document fondateur sur les critères d'un bon problème](https://www.strategie.gouv.fr/)",
        "[**Eric Ries** — *The Lean Startup* (2011)](http://theleanstartup.com/) : l'apprentissage validé, les métriques actionnables et le pivot.",
        "[**Marty Cagan** — *Inspired* (2018)](https://www.svpg.com/books/inspired-how-to-create-tech-products-customers-love-2nd-edition/) : aligner le problème sur une North Star Metric cohérente.",
        "[**Nassim Taleb** — *Antifragile* (2012)](https://www.penguinrandomhouse.com/books/176227/antifragile-by-nassim-nicholas-taleb/) : la réversibilité et l'optionnalité comme critères de décision face à l'incertitude.",
    ])

    nav_buttons()


# ═══════════════════════════════════════════════════════════
# ÉTAPE 8 — PORTRAIT DU PROBLÈME
# ═══════════════════════════════════════════════════════════
elif step == 8:
    zoom_badge("global")
    st.markdown("## 🎨 Portrait du Problème")

    st.markdown("""
### Votre problème, tel qu'il a émergé

Ce portrait est construit à partir de toutes vos réponses précédentes.  
**Ce n'est pas une solution.** C'est un miroir — votre problème mieux formulé.  
Il est fait pour être partagé, contesté, affiné avec vos parties prenantes.
""")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📌 Problème initial**")
        st.info(a("problem_initial") or "*Non renseigné*")
        st.markdown("**🌍 Système producteur**")
        st.info(a("system_name") or "*Non renseigné*")
        st.markdown("**🔁 Boucle circulaire**")
        st.info(a("circular_loop") or "*Non renseigné*")
    with col2:
        st.markdown("**🎯 Cause racine**")
        st.info(a("root_cause") or "*Non renseigné*")
        st.markdown("**🌐 Type de problème (Cynefin)**")
        st.info(a("cynefin") or "*Non renseigné*")
        st.markdown("**💡 Insight du recadrage**")
        st.info(a("reframe_insight") or "*Non renseigné*")

    st.markdown("---")
    st.markdown("### 🤖 Synthèse générée par IA")
    st.caption("L'IA synthétise vos réponses pour produire un portrait structuré de votre problème — dans une perspective systémique.")

    if st.button("✨ Générer le Portrait du Problème", type="primary"):
        with st.spinner("Synthèse en cours..."):
            try:
                ans = st.session_state.answers
                prompt = f"""Tu es un expert reconnu en systémique et en transition écologique, 
dans la lignée de Donella Meadows, Peter Senge et Kees Dorst.

Un utilisateur expert vient de compléter un exercice de problématisation systémique approfondie. 
Voici l'ensemble de ses réponses :

**Problème initial :** {ans.get('problem_initial', 'N/A')}
**Domaine :** {ans.get('domain', 'N/A')}
**Système producteur identifié :** {ans.get('system_name', 'N/A')}
**Boucle circulaire :** {ans.get('circular_loop', 'N/A')}
**Qui bénéficie du statu quo :** {ans.get('who_benefits', 'N/A')}
**Qui souffre :** {ans.get('sufferers', 'N/A')}
**Qui décide :** {ans.get('deciders', 'N/A')}
**Invisibles :** {ans.get('invisible', 'N/A')}
**Client prioritaire :** {ans.get('primary_actor', 'N/A')}
**Cause racine :** {ans.get('root_cause', 'N/A')}
**Type Cynefin :** {ans.get('cynefin', 'N/A')}
**Tensions identifiées :** {ans.get('t1_a', '')} ↔ {ans.get('t1_b', '')} / {ans.get('t2_a', '')} ↔ {ans.get('t2_b', '')}
**Perspective la plus inconfortable :** {ans.get('most_uncomfortable', 'N/A')}
**Insight du recadrage :** {ans.get('reframe_insight', 'N/A')}

Produis un "Portrait du Problème" structuré et rigoureux en 4 parties :

**1. Le problème en une phrase**
Une formulation précise, systémique, centrée sur le client prioritaire. Pas de jargon. 
Utilisez si pertinent la structure "How Might We" ou une formulation narrative puissante.

**2. Ce qui maintient le problème en place**
Les 2-3 mécanismes clés identifiés (boucles circulaires, verrouillages institutionnels, 
tensions non résolues). Sois précis et référence les éléments fournis.

**3. Ce que ce problème révèle**
Sur le système plus large, ses impensés, ses angles morts, ses tensions constitutives. 
Quelle est la leçon systémique de ce problème ?

**4. La prochaine question à se poser**
Pas une solution. Pas une recommandation. La question qui permettra d'approfondir encore 
la compréhension — celle qu'on ne peut poser qu'après avoir fait ce travail.

Ton ton : expert systémicien, rigoureux, nuancé, non moralisateur. 
Langue : français. Longueur : 350-450 mots."""

                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": st.secrets["ANTHROPIC_API_KEY"],
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 1000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                data = response.json()
                portrait = data["content"][0]["text"]
                save("portrait", portrait)

            except Exception as e:
                st.error(f"Erreur lors de la génération : {e}")

    if a("portrait"):
        st.markdown(
            f'<div class="portrait-box">{a("portrait").replace(chr(10), "<br>")}</div>',
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.success("""
### ✅ Votre portrait est prêt

Ce portrait n'est pas une réponse. C'est un point de départ.

**Prochaines étapes recommandées :**
1. **Partagez** ce portrait avec des parties prenantes pour valider ou invalider les hypothèses
2. **Confrontez-le au terrain** : allez observer, écouter, expérimenter à petite échelle
3. **Revenez le reformuler** dans 3-4 semaines avec de nouvelles données de terrain
4. **Résistez** à toute pression pour passer aux solutions avant d'avoir validé le problème
""")

        if st.button("⬇️ Copier le portrait (texte brut)"):
            st.code(a("portrait"), language=None)

    nav_buttons()
