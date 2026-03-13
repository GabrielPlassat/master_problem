# 🎯 L'Art de Problématiser — README

Outil interactif pour aider des experts à mieux poser leur problème,  
dans une perspective systémique, avant de chercher des solutions.

---

## 🚀 Déploiement sur Streamlit Cloud (recommandé)

1. **Créez un nouveau repo GitHub** (public ou privé)
2. **Déposez** `app.py` et `requirements.txt` à la racine du repo
3. **Allez sur** [share.streamlit.io](https://share.streamlit.io)
4. **Connectez votre repo GitHub** et sélectionnez `app.py` comme fichier principal
5. **Ajoutez votre clé API Anthropic** dans les secrets Streamlit :
   - Dans Streamlit Cloud → votre app → Settings → Secrets
   - Ajoutez : `ANTHROPIC_API_KEY = "sk-ant-..."`
6. Cliquez **Deploy** — c'est tout !

---

## 💻 Lancement local (optionnel)

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 🔑 Configuration de la clé API Anthropic

L'étape finale (Portrait du Problème) utilise l'API Claude pour générer une synthèse.

**Pour Streamlit Cloud :** Ajoutez dans Settings → Secrets :
```toml
ANTHROPIC_API_KEY = "sk-ant-votre-clé-ici"
```

**Pour un test local sans clé :** L'outil fonctionne entièrement sans API jusqu'à l'étape 8.
La génération du portrait sera simplement désactivée.

---

## 📐 Structure de l'outil

| Étape | Nom | Zoom |
|-------|-----|------|
| 0 | Accueil & contexte | — |
| 1 | Le Système Producteur | 🌍 Global |
| 2 | Cartographie des Acteurs | 🔍 Local |
| 3 | Les 5 Pourquoi Systémiques | 🔄 Aller-retour |
| 4 | Positionnement Cynefin | 🌍 Global |
| 5 | Carte des Tensions | 🔄 Aller-retour |
| 6 | Test du Fantôme | 🔄 Aller-retour |
| 7 | Évaluation du Problème | 🔍 Local |
| 8 | Portrait du Problème | 🌍 Global |

---

## 📚 Références principales intégrées

- **Marty Cagan** — *Inspired* (2018)
- **Donella Meadows** — *Thinking in Systems* (2008)
- **Peter Senge** — *La Cinquième Discipline* (1990)
- **Dave Snowden** — Cadre Cynefin (1999)
- **Kees Dorst** — *Frame Innovation* (2015)
- **Rittel & Webber** — Wicked Problems (1973)
- **Marius Ursache** — Problem Statement Canvas
- **Tony Ulwick** — Jobs-to-be-Done

---

*Outil conçu pour des experts de la transition écologique et de l'innovation systémique.*
