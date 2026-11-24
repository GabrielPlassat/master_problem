# 🌿 Formulateur Stratégique — Transition Écologique

Outil Streamlit qui aide un expert à **bien poser son problème** avant de chercher des solutions,
puis à **repérer ce qui existe déjà** (communs, solutions, acteurs, données ouvertes) pour ne pas
repartir de zéro.

---

## 📐 Les 11 phases

| Phase | Nom | Ce qu'elle fait |
|-------|-----|-----------------|
| 1 | Ancrage | Décrire le problème, avec des documents (PDF, Word, rapport SofIA) |
| 2 | Miroir des Impossibles | Cas historiques où les experts se sont trompés |
| 3 | Scout Technologique | Technologies venues d'autres domaines |
| 4 | Décomposition | Choisir un sous-problème |
| 5 | Ressources & Contraintes | Budget, équipe, délais, objectifs |
| 6 | Test de Cohérence | Le sous-problème est-il à votre portée ? |
| 7 | Formulation Finale | « Comment pourrions-nous… », indicateurs, risques |
| 8 | Communs & Ressources | Communs, projets, acteurs et connaissances du [wiki de la Fabrique des Mobilités](https://wiki.lafabriquedesmobilites.fr) |
| 9 | Solutions & Acteurs | Solutions recensées par [France Mobilités](https://www.francemobilites.fr/solutions) et leurs porteurs |
| 10 | Données Ouvertes | Jeux de données et API de [data.gouv.fr](https://www.data.gouv.fr), catalogue [Melodi de l'INSEE](https://catalogue-donnees.insee.fr) |
| 11 | Synthèse & Export | Ressources retenues, feuille de route, fiche Word |

Dans les phases 8 à 10, l'outil extrait des mots-clés du problème (modifiables), présélectionne les
fiches correspondantes dans chaque source, puis Claude choisit les plus pertinentes et explique
comment s'en servir. Cochez **Retenir** pour les garder dans la fiche finale.

## 💾 Sauvegarder et reprendre

- **💾 Sauvegarder ma progression** (en bas de chaque page et dans la barre latérale) télécharge un
  fichier `.json` avec tout votre travail.
- **📂 Reprendre une sauvegarde** (barre latérale) recharge ce fichier et vous ramène à l'étape où
  vous étiez, par exemple directement au problème formulé en phase 7.
- Les phases déjà atteintes sont cliquables dans la barre latérale pour revenir en arrière.

---

## 🚀 Déploiement sur Streamlit Cloud

1. Sur [share.streamlit.io](https://share.streamlit.io), connectez ce dépôt et choisissez `app.py`.
2. Dans **Settings → Secrets**, ajoutez la clé de l'API Claude :
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
3. Cliquez sur **Deploy**.

Option : le wiki de la Fabrique des Mobilités n'accepte que les robots autorisés. L'outil utilise
par défaut le nom autorisé `XD-Chatbot`. S'il change, ajoutez dans les secrets :
```toml
WIKI_USER_AGENT = "nouveau-nom"
```

## 📁 Fichiers

| Fichier | Rôle |
|---------|------|
| `app.py` | L'application (toutes les phases) |
| `sources.py` | La connexion au wiki, à France Mobilités, à data.gouv.fr et à l'INSEE |
| `requirements.txt` | Les bibliothèques Python nécessaires |

## ⚠️ Limites à connaître

- Les sources sont rechargées au plus une fois par jour (mise en cache). Le catalogue France
  Mobilités pèse environ 15 Mo : la première recherche prend quelques secondes de plus.
- La présélection repose sur des mots-clés : une fiche mal décrite peut être manquée. Ajustez les
  mots-clés si les résultats semblent incomplets.
- Les pages « Connaissance » du wiki sont repérées par leur type de page (elles sont rangées dans la
  catégorie « Référentiel »).

---

## 📚 Références intégrées

Cynefin (Snowden), Problem Statement Canvas, Jobs-to-be-Done, Double Diamant, « How Might We » (IDEO),
Frame Innovation (Dorst), *Inspired* (Cagan).
