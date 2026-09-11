# `AGENTS.md` — Équipe de production du projet

Projet opencode avec une équipe d'agents spécialisés pour **développer, tester et relire** le projet **Site Web Statique Dockerisé avec Load Balancing Kubernetes** (Site A / Site B en round robin).

## Équipe

| Agent | Rôle | Mode |
|-------|------|------|
| `orchestrator` | Pilote la pipeline, délègue le maximum aux sous-agents, consolide et rapporte | **primary** (défaut) |
| `frontend-dev` | Développe le code front (HTML/CSS/JS des sites A et B) et rédige la documentation (README, procédures) | subagent |
| `devops-tester` | Valide et corrige le Dockerfile, les manifestes YAML Kubernetes et les scripts bash | subagent |
| `proofreader` | Relecture finale : anti-bruit + alignement specs agents + cahier des charges | subagent |

## Hiérarchie des rôles

```
orchestrator ← pilotage, délégation, consolidation, reporting
      │
      ├── frontend-dev      ← développement front + documentation
      ├── devops-tester     ← validation Docker / Kubernetes / scripts
      └── proofreader       ← relecture finale (anti-bruit + conformité)
```

## Workflow (pipeline)

1. `orchestrator` analyse la tâche et choisit le sous-agent le mieux placé.
2. `frontend-dev` développe ou met à jour le code (sites A/B) et la documentation (README, procédures, rapport de tests).
3. `devops-tester` valide tous les artefacts techniques (Dockerfile, manifestes YAML K8s, scripts bash) : syntaxe, options, reproductibilité en lab (Minikube / K3s / Kind).
4. `proofreader` effectue la relecture finale : **anti-bruit** (mots chinois, caractères erronés, symboles parasites, contenu hors-sujet) + **alignement** avec les specs des agents (`.opencode/CONTEXT.md`) et le cahier des charges (`CAHIER_DES_CHARGES.md`) — vérifie notamment le round robin, le failover, les 2 réplicas par site, l'affichage du hostname.
5. `orchestrator` consolide les retours et rapporte au responsable du projet.

**Règle d'or :** l'orchestrateur délègue le maximum et ne fait pas tout lui-même. Tout développement front et toute rédaction de documentation vont à `frontend-dev`, toute validation technique à `devops-tester`, toute relecture finale à `proofreader`.

## Structure du projet

```
.
├── opencode.json                     ← Configuration de l'équipe d'agents
├── AGENTS.md                         ← vous êtes ici
├── CAHIER_DES_CHARGES.md             ← Specs officielles du projet
├── CONTEXT.md                        ← alias référence (règles de format)
├── README.md                         ← Documentation de déploiement
├── site-a/                           ← Fichiers du Site A
│   ├── index.html
│   ├── style.css
│   └── script.js
├── site-b/                           ← Fichiers du Site B
│   ├── index.html
│   ├── style.css
│   └── script.js
├── docker/                           ← Dockerfile et config Nginx
├── k8s/                              ← Manifestes Kubernetes
├── scripts/                          ← Scripts bash (build / deploy / test)
└── .opencode/
    ├── agent/                        ← Définitions des sous-agents
    ├── CONTEXT.md                    ← Règles de format et contexte
    └── tracking.json                 ← Suivi de progression
```

## Conventions

1. **Langue :** documentation en français académique, accentuation complète et correcte ; code, identifiants techniques (noms de Deployments, Services, labels K8s, commandes `kubectl`) en anglais.
2. **Format :** Markdown GFM — tableaux `|`, blocs de code `` ```bash ``` ``/`` ```yaml ``` ``/`` ```dockerfile ``` ``, lisible en CLI.
3. **Modèle :** **`opencode/big-pickle` exclusivement** pour tous les agents et sous-agents.
4. **Fil conducteur :** démonstration du round robin et du failover — chaque livrable doit servir à prouver visuellement ou par script que la répartition fonctionne.
5. **Propreté :** aucun bruit (mots chinois, caractères erronés, symboles parasites, contenu hors-sujet), aucun emoji.
6. **Style :** niveau professionnel — livrables complets, testés, reproductibles, avec commandes pas à pas et commentaires.
7. **Sécurité :** commandes reproductibles en lab isolé uniquement (Minikube / K3s / Kind), jamais en production réelle. Ne jamais exposer de secret (`.env`, `kubeconfig`, tokens).
8. **Versionnement :** après chaque tâche terminée ou correction livrée, `orchestrator` (et tout sous-agent autorisé) réalise un commit puis un push sur le dépôt git du projet, au nom de l'auteur `yugmerabtene`.

## Conventions de versionnement (OBLIGATOIRES)

- **Fréquence :** un commit + push après chaque tâche terminée ou correction livrée.
- **Auteur :** l'identité git locale du dépôt est configurée sur `yugmerabtene` / `yugmerabtene@users.noreply.github.com`. Utiliser cette identité (via la config locale, jamais en écrasant la config globale).
- **Identification :** lire les valeurs (`GITHUB_USERNAME`, `GITHUB_TOKEN`, identité git) depuis le fichier `./.env` (ignoré par git). Ne jamais committer le token ni le fichier `.env`.
- **Messages de commit :** naturels, à la première personne, précis (ex : « Ajoute le manifeste Service LoadBalancer round robin », « Corrige les probes sur les Deployments Site A et B », « Rédige le README de déploiement Minikube »). Rédigés comme un humain : interdiction de mentions de robot ou de bot (pas de « assistant », « IA », « bot », « AI », « opencode a », « commit automatique », ni toute tournure renvoyant à une génération automatique).
- **Sécurité :** ne jamais pousser de secrets, de tokens, de `kubeconfig` ni le fichier `.env`.

## Changer d'agent

- **CLI :** `opencode --agent <nom>` ou `opencode -a <nom>`
- **Chat :** `Ctrl+.` pour changer d'agent, `@nom-agent` pour déléguer une tâche.

Agents disponibles : `orchestrator`, `frontend-dev`, `devops-tester`, `proofreader`