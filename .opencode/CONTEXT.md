# Contexte du projet — Site Web Statique Dockerisé avec Load Balancing Kubernetes

Ce fichier centralise toutes les spécifications du projet. Les agents (`orchestrator`,
`frontend-dev`, `devops-tester`, `proofreader`) le lisent au début de chaque session
pour garder les specs en tête. Il est la source de vérité pour le **quoi** et le
**comment technique**. Le **qui fait quoi** reste dans `opencode.json`.

---

## 1. Objet du projet

Produire un site web statique conteneurisé, déployé sur un cluster Kubernetes avec
un load balancer en mode **Round Robin**, et démontrer la répartition de charge et
le failover via deux versions distinctes du site : **Site A** et **Site B**.

Objectifs pédagogiques et techniques :
- Développer un site statique propre (HTML5 / CSS3 / JS vanilla).
- Le conteneuriser avec Docker (image légère, serveur Nginx Alpine).
- Le déployer sur Kubernetes avec un `Service` de type `LoadBalancer`.
- Vérifier visuellement et par script l'alternance Round Robin.
- Vérifier le failover (suppression de pod, pod non prêt, scale down/up).

---

## 2. Périmètre

### Inclus
- Développement du site statique (Site A et Site B).
- Création des images Docker (une par site).
- Manifestes Kubernetes : `Deployment`, `Service`, `ConfigMap`.
- Configuration du load balancing Round Robin (`sessionAffinity: None`).
- Scripts bash : `build.sh`, `deploy.sh`, `test-loadbalancer.sh`.
- Documentation (`README.md`) et rapport de tests.
- Tests fonctionnels et de failover.

### Exclu
- Base de données, backend, authentification.
- HTTPS/TLS (optionnel, hors scope initial).
- CI/CD complet (Jenkins, GitLab CI, etc.).
- Monitoring avancé (Prometheus/Grafana) — évolution possible.

---

## 3. Spécifications fonctionnelles

### 3.1 Site statique
| Élément | Spécification |
|---------|---------------|
| Langages | HTML5, CSS3, JavaScript vanilla |
| Page principale | `index.html` affichant clairement « SITE A » ou « SITE B » |
| Style | CSS responsive, moderne, léger |
| JS | Affiche dynamiquement le hostname du conteneur (preuve de l'alternance) |
| Assets | Favicon et images légères (optionnel) |

### 3.2 Contenu obligatoire pour la démonstration
- Affichage en grand : **« SITE A »** (bleu) ou **« SITE B »** (vert).
- Affichage du `hostname` du conteneur (variable d'environnement ou fichier).
- Horodatage ou compteur pour prouver la fraîcheur de la réponse.
- Code couleur distinct entre A et B.

### 3.3 Load Balancer
- Type : Kubernetes `Service` de type `LoadBalancer`.
- Algorithme : **Round Robin** (`sessionAffinity: None`).
- Port exposé : 80 (HTTP).
- Réplicas Site A : **2**.
- Réplicas Site B : **2**.

### 3.4 Failover
- Liveness et Readiness Probes sur chaque `Deployment`.
- Redémarrage automatique des pods défaillants.
- Retrait automatique des pods non prêts du load balancing.
- Redirection transparente vers les pods sains.

---

## 4. Architecture cible

```
                    ┌──────────────────┐
                    │   Utilisateur    │
                    └────────┬─────────┘
                             │ HTTP
                    ┌────────▼─────────┐
                    │  LoadBalancer    │
                    │  (Round Robin)   │
                    └────────┬─────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
        ┌───────▼───────┐         ┌───────▼───────┐
        │  Site A       │         │  Site B       │
        │  (2 replicas) │         │  (2 replicas) │
        └───────────────┘         └───────────────┘
```

---

## 5. Stack technique

| Composant | Technologie |
|-----------|-------------|
| Frontend | HTML5 / CSS3 / JavaScript vanilla |
| Serveur web | Nginx Alpine |
| Conteneurisation | Docker |
| Orchestration | Kubernetes (Minikube / K3s / Kind) |
| Load Balancing | Service K8s type LoadBalancer |
| Scripts | Bash |

---

## 6. Arborescence du projet

```
projet/
├── .opencode/
│   ├── CONTEXT.md            # ce fichier
│   └── tracking.json         # suivi de progression
├── docker/
│   ├── Dockerfile.site-a
│   ├── Dockerfile.site-b
│   └── nginx.conf
├── site-a/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── site-b/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── k8s/
│   ├── deployment-site-a.yaml
│   ├── deployment-site-b.yaml
│   ├── service-loadbalancer.yaml
│   └── configmap.yaml
├── scripts/
│   ├── build.sh
│   ├── deploy.sh
│   └── test-loadbalancer.sh
├── CAHIER_DES_CHARGES.md
├── README.md
└── .env                      # gitignore — NE PAS COMMITER
```

---

## 7. Contraintes

### 7.1 Techniques
- Compatible Minikube, K3s, Kind et clusters cloud (GKE, EKS, AKS).
- Images Docker légères (< 50 Mo chacune).
- Temps de démarrage des pods < 30 s.
- Site 100 % statique, aucune dépendance externe.

### 7.2 Sécurité
- Conteneurs exécutés en utilisateur non-root.
- Aucun secret en clair dans les manifestes.
- Scan d'images recommandé (Trivy, optionnel).
- Ne jamais commiter `.env`, `kubeconfig` ni tokens.

### 7.3 Performance
- Temps de réponse < 100 ms.
- Support minimum de 100 requêtes/seconde.

---

## 8. Règles de format et de qualité

- **Langue** : français académique accentué.
- **Style** : professionnel, précis, reproductible.
- **Bruit à proscrire** (vérifié par le proofreader) :
  - Mots ou caractères chinois.
  - Symboles parasites (`�`, `?` isolés, `\\`, etc.).
  - Espaces insécables mal placées, encodage cassé.
- **Cohérence** : toute modification de spec doit être répercutée dans ce fichier
  et dans `CAHIER_DES_CHARGES.md`.

---

## 9. Workflow de production

1. **Analyse** — l'orchestrateur identifie la tâche et le sous-agent adapté.
2. **Délégation** :
   - Rédaction (site, docs, rapport) → `frontend-dev`.
   - Validation technique (Dockerfile, YAML, scripts) → `devops-tester`.
3. **Consolidation** — l'orchestrateur applique les corrections via le sous-agent concerné.
4. **Relecture finale** → `proofreader` (obligatoire avant validation).
5. **Versionnement** — commit + push après chaque tâche ou correction.

---

## 10. Règles de versionnement git

- Dépôt git du projet, auteur unique : **yugmerabtene**.
- Commit + push **après chaque tâche terminée ou correction livrée**.
- Messages de commit :
  - Clairs, précis, à la **première personne**, style humain.
  - Exemples autorisés :
    - « Ajoute le manifeste Service LoadBalancer round robin »
    - « Corrige les probes sur les Deployments Site A et B »
    - « Rédige le README de déploiement Minikube »
  - Mentions interdites : `assistant`, `IA`, `AI`, `bot`, `opencode a`,
    `commit automatique`, ou toute tournure suggérant une génération automatique.
- Identité et token lus depuis `.env` (gitignore).
- **Ne jamais** commiter `.env`, `kubeconfig`, tokens ou tout autre secret.

---

## 11. Critères d'acceptation

- [ ] Le site est accessible via l'IP du LoadBalancer.
- [ ] Les requêtes alternent entre Site A et Site B (Round Robin vérifié par script).
- [ ] La suppression d'un pod n'interrompt pas le service.
- [ ] Les pods redémarrent automatiquement en cas de défaillance.
- [ ] La documentation permet à un tiers de reproduire le déploiement.
- [ ] Tous les tests du cahier des charges passent avec succès.

---

## 12. Évolutions possibles

- HTTPS via cert-manager + Let's Encrypt.
- Ingress Controller (Nginx / Traefik) avec routage par chemin.
- Monitoring Prometheus + Grafana.
- CI/CD GitHub Actions.
- Déploiement multi-cluster (haute disponibilité géographique).

---

## Notes d'utilisation

| Fichier | Rôle | Fréquence de mise à jour |
|---------|------|--------------------------|
| `opencode.json` | Qui fait quoi (orchestration) | Rarement |
| `.opencode/CONTEXT.md` | Sur quoi on travaille (specs) | À chaque évolution de spec |
| `CAHIER_DES_CHARGES.md` | Le quoi exhaustif (livrables, planning, tests) | À chaque jalon |
| `.opencode/tracking.json` | Où on en est (progression) | À chaque tâche terminée |

