# Cahier des charges -- Site Web Statique Dockerisé avec Load Balancing Kubernetes

| Champ | Valeur |
|-------|--------|
| **Version** | 1.0.0 |
| **Date** | 2026-09-10 |
| **Auteur** | yugmerabtene |
| **Statut** | En cours (Phase 6 : Documentation) |

---

## 1. Objet du projet

Ce projet vise a deployer un site web statique conteneurise sur un cluster
Kubernetes, avec un Service de type `LoadBalancer` assurant la distribution de charge
en mode **Round Robin**. Deux versions distinctes du site -- **Site A** et **Site B**
-- sont deployees simultanement pour demonstrer visuellement :

- La **repartition de charge** : les requetes entrantes alternent entre les pods du
  Site A et ceux du Site B.
- Le **failover** : la suppression ou la defaillance d'un pod n'interrompt pas le
  service ; le ReplicaSet recree automatiquement un nouveau pod.

### Objectifs pedagogiques et techniques

- Developper un site statique propre en HTML5 / CSS3 / JavaScript vanilla.
- Le conteneuriser avec Docker (image basee sur nginx:alpine, utilisateur non-root).
- Le deployer sur Kubernetes avec un `Service` de type `LoadBalancer`.
- Verifier visuellement et par script l'alternance Round Robin.
- Verifier le failover (suppression de pod, pod non pret, scale down/up).

---

## 2. Perimetre

### Inclus

| Element | Description |
|---------|-------------|
| Sites A et B | Developpement des pages statiques (HTML, CSS, JS) |
| Docker | Dockerfiles, configuration Nginx, images optimisees |
| Kubernetes | Manifestes : Deployments, Service LoadBalancer, ConfigMap |
| Round Robin | Configuration `sessionAffinity: None` sur le Service |
| Scripts bash | `build.sh`, `deploy.sh`, `test-loadbalancer.sh` |
| Documentation | `README.md`, `CAHIER_DES_CHARGES.md`, `rapport_tests.md` |
| Tests | Tests fonctionnels (round robin), failover et recuperation |

### Exclu

| Element | Justification |
|---------|---------------|
| Base de donnees | Projet purement statique, aucun backend |
| Backend / API | Aucune logique serveur necessaire |
| Authentication | Hors scope du projet |
| HTTPS / TLS | Optionnel, hors scope initial |
| CI/CD complet | Jenkins, GitLab CI, GitHub Actions hors scope |
| Monitoring avance | Prometheus / Grafana -- evolution possible |

---

## 3. Specifications fonctionnelles

### 3.1 Sites statiques

| Element | Site A | Site B |
|---------|--------|--------|
| Titre affiche | « SITE A » | « SITE B » |
| Couleur principale | `#2196F3` (bleu) | `#4CAF50` (vert) |
| Langages | HTML5, CSS3, JS vanilla | HTML5, CSS3, JS vanilla |
| Responsive | Oui (media query 480px) | Oui (media query 480px) |
| Dependance externe | Aucune | Aucune |

### 3.2 Contenu obligatoire pour la demonstration

- Affichage en grand du nom du site (« SITE A » ou « SITE B »).
- Affichage dynamique du hostname du conteneur (variable d'environnement `HOSTNAME`,
  remplacee par `sed` au demarrage via l'entrypoint).
- Horodatage mis a jour en temps reel (actualisation toutes les secondes via
  `setInterval`).
- Compteur de requetes local.
- Code couleur distinct entre les deux sites.

### 3.3 Load Balancer

| Parametre | Valeur |
|-----------|--------|
| Type | Kubernetes `Service` de type `LoadBalancer` |
| Algorithme | Round Robin (`sessionAffinity: None`) |
| Port d'entree | 80 (HTTP) |
| TargetPort | 8080 (conteneur Nginx) |
| Selecteur | `tier: web` (couvre les deux Deployments) |
| Replicas Site A | 2 |
| Replicas Site B | 2 |
| **Total pods** | **4** |

### 3.4 Failover

| Parametre | Valeur |
|-----------|--------|
| Liveness probe | HTTP GET `/` sur port 8080, periode 10 s, seuil 3 |
| Readiness probe | HTTP GET `/` sur port 8080, periode 5 s, seuil 3 |
| Comportement | Redemarrage automatique des pods defaillants |
| Retrait | Retrait automatique des pods non prets du Load Balancing |
| Recuperation | ReplicaSet maintient le nombre de replicas souhaite |

---

## 4. Architecture cible

```
                    +------------------+
                    |    Utilisateur   |
                    +--------+---------+
                             | HTTP
                    +--------v---------+
                    |   LoadBalancer   |
                    |  (Round Robin)   |
                    +--------+---------+
                             |
                +------------+------------+
                |                         |
        +-------v-------+         +-------v-------+
        |   Site A      |         |   Site B      |
        | (2 replicas)  |         | (2 replicas)  |
        +---------------+         +---------------+
```

### Description des composants

- **Utilisateur** : envoie une requete HTTP vers l'adresse du LoadBalancer.
- **LoadBalancer** : Service Kubernetes de type `LoadBalancer` repartissant les
  requetes en round robin sur tous les pods labellises `tier: web`.
- **Site A** : Deployment de 2 pods servissant la page « SITE A » (theme bleu).
  Chaque pod affiche son propre hostname et un horodatage en temps reel.
- **Site B** : Deployment de 2 pods servissant la page « SITE B » (theme vert).
  Meme comportement dynamique que le Site A.

---

## 5. Stack technique

| Composant | Technologie | Version / Reference |
|-----------|-------------|---------------------|
| Frontend | HTML5 / CSS3 / JavaScript vanilla | -- |
| Serveur web | Nginx | `nginx:alpine` |
| Conteneurisation | Docker | 20.10+ |
| Orchestration | Kubernetes | 1.25+ (Minikube / K3s / Kind) |
| Load Balancing | Service K8s type LoadBalancer | -- |
| Scripts | Bash | 4.0+ |
| Tests | curl | 7.0+ |

---

## 6. Arborescence du projet

```
.
├── docker/                           Configuration Docker et Nginx
│   ├── Dockerfile.site-a             Dockerfile du Site A
│   ├── Dockerfile.site-b             Dockerfile du Site B
│   └── nginx.conf                    Configuration Nginx partagee
├── site-a/                           Fichiers du Site A
│   ├── index.html                    Page principale (HTML5)
│   ├── style.css                     Styles (CSS3 responsive)
│   └── script.js                     Logique dynamique (JS vanilla)
├── site-b/                           Fichiers du Site B
│   ├── index.html                    Page principale (HTML5)
│   ├── style.css                     Styles (CSS3 responsive)
│   └── script.js                     Logique dynamique (JS vanilla)
├── k8s/                              Manifestes Kubernetes
│   ├── deployment-site-a.yaml        Deployment Site A (2 replicas)
│   ├── deployment-site-b.yaml        Deployment Site B (2 replicas)
│   ├── service-loadbalancer.yaml     Service LoadBalancer (round robin)
│   └── configmap.yaml                ConfigMap Nginx
├── scripts/                          Scripts Bash
│   ├── build.sh                      Construction des images Docker
│   ├── deploy.sh                     Deploiement sur Kubernetes
│   └── test-loadbalancer.sh          Tests round robin, failover, recuperation
├── CAHIER_DES_CHARGES.md             Ce fichier
├── rapport_tests.md                  Rapport de tests
├── README.md                         Documentation de deploiement
└── .env                              Variables d'environnement (gitignore)
```

---

## 7. Contraintes

### 7.1 Techniques

| Contrainte | Valeur |
|------------|--------|
| Taille maximale des images Docker | < 50 Mo chacune |
| Temps de demarrage des pods | < 30 secondes |
| Nature du site | 100 % statique, aucune dependance externe |
| Compatibilite clusters | Minikube, K3s, Kind, GKE, EKS, AKS |

### 7.2 Securite

| Contrainte | Detail |
|------------|--------|
| Utilisateur non-root | `appuser` (UID 1001), `runAsNonRoot: true` dans les Deployments |
| Secrets | Aucun secret en clair dans les manifestes Kubernetes |
| Scan d'images | Trivy recommande (optionnel) |
| Fichiers sensibles | `.env`, `kubeconfig`, tokens jamais committes |

### 7.3 Performance

| Contrainte | Valeur |
|------------|--------|
| Temps de reponse | < 100 ms |
| Debit minimum | 100 requetes/seconde |
| Compression | Gzip active dans Nginx |
| Cache | Desactive en developpement (`no-cache, no-store, must-revalidate`) |

---

## 8. Criterees d'acceptation

| # | Critere | Statut |
|---|---------|--------|
| 1 | Le site est accessible via l'IP du LoadBalancer (ou en port-forward) | En attente (lab) |
| 2 | Les requetes alternent entre Site A et Site B (round robin verifie par script) | En attente (lab) |
| 3 | La suppression d'un pod n'interrompt pas le service | En attente (lab) |
| 4 | Les pods redemarrent automatiquement en cas de defaillance | En attente (lab) |
| 5 | La documentation permet a un tiers de reproduire le deploiement | En cours |
| 6 | Tous les tests du cahier des charges passent avec succes | En attente (lab) |
| 7 | Conformite du code : analyse statique des manifestes, Dockerfiles et scripts | Verifie (code) |
| 8 | Aucun bruit dans les livrables (mots chinois, caracteres parasites, emoji) | En cours |

---

## 9. Planning

### Phase 1 : Developpement des sites

| Champ | Valeur |
|-------|--------|
| Statut | Termine |
| Livrables | `site-a/`, `site-b/` (HTML, CSS, JS) |
| Details | Sites A et B developpes en HTML5, CSS3, JS vanilla. Affichage du hostname, horodatage temps reel, compteur de requetes. CSS responsive. |

### Phase 2 : Dockerisation

| Champ | Valeur |
|-------|--------|
| Statut | Termine |
| Livrables | `docker/Dockerfile.site-a`, `docker/Dockerfile.site-b`, `docker/nginx.conf` |
| Details | Images basees sur nginx:alpine, utilisateur non-root (UID 1001), entrypoint remplacant le placeholder `{{HOSTNAME}}`, port 8080. Taille cible < 50 Mo. |

### Phase 3 : Manifestes Kubernetes

| Champ | Valeur |
|-------|--------|
| Statut | Termine |
| Livrables | `k8s/deployment-site-a.yaml`, `k8s/deployment-site-b.yaml`, `k8s/service-loadbalancer.yaml`, `k8s/configmap.yaml` |
| Details | 2 replicas par site, Service LoadBalancer avec `sessionAffinity: None`, ConfigMap Nginx, liveness et readiness probes, ressources limitees (100m CPU, 64Mi RAM). |

### Phase 4 : Scripts

| Champ | Valeur |
|-------|--------|
| Statut | Termine |
| Livrables | `scripts/build.sh`, `scripts/deploy.sh`, `scripts/test-loadbalancer.sh` |
| Details | Script de construction avec verification de taille, script de deploiement avec attente de convergence, script de tests (round robin, failover, recuperation). |

### Phase 5 : Tests

| Champ | Valeur |
|-------|--------|
| Statut | Termine (resultats en attente du lab) |
| Livrables | `rapport_tests.md` |
| Details | Protocole de test defini pour 5 scenarios. Analyse statique du code conformee. Tests fonctionnels a executer en environnement de laboratoire (Minikube, K3s ou Kind). |

### Phase 6 : Documentation

| Champ | Valeur |
|-------|--------|
| Statut | En cours |
| Livrables | `README.md`, `CAHIER_DES_CHARGES.md` |
| Details | Documentation de deploiement (README) et cahier des charges complet (ce document). |

---

## 10. Evolutions possibles

| Evolution | Priorite | Description |
|-----------|----------|-------------|
| HTTPS | Haute | Cert-manager + Let's Encrypt pour le TLS |
| Ingress Controller | Moyenne | Nginx ou Traefik avec routage par chemin |
| Monitoring | Moyenne | Prometheus + Grafana pour la supervision |
| CI/CD | Moyenne | GitHub Actions pour la construction et le deploiement automatiques |
| Multi-cluster | Basse | Deploiement geographique pour la haute disponibilite |
| Autoscaling | Basse | Horizontal Pod Autoscaler (HPA) adapte a la charge |

---

## 11. Conformite

### Analyse statique

| Critere | Specification | Statut |
|---------|---------------|--------|
| Site A affiche « SITE A » en bleu | `#2196F3` (`--color-primary` dans `site-a/style.css`) | Conforme |
| Site B affiche « SITE B » en vert | `#4CAF50` (`--color-primary` dans `site-b/style.css`) | Conforme |
| Hostname dynamique | Placeholder `{{HOSTNAME}}` remplace par `sed` dans l'entrypoint | Conforme |
| Horodatage temps reel | `setInterval(updateTimestamp, 1000)` dans `script.js` | Conforme |
| CSS responsive | Media query `@media (max-width: 480px)` | Conforme |
| Aucune dependance externe | HTML5, CSS3, JS vanilla uniquement | Conforme |
| Images < 50 Mo | `nginx:alpine` + fichiers statiques uniquement | Conforme |
| Conteneurs non-root | `USER appuser` (UID 1001), `runAsNonRoot: true` | Conforme |
| Port 8080 | `EXPOSE 8080`, `containerPort: 8080` | Conforme |
| 2 replicas par site | `replicas: 2` dans les Deployments | Conforme |
| Round robin | `sessionAffinity: None` dans le Service | Conforme |
| Probes | Liveness (10 s) et readiness (5 s) sur port 8080 | Conforme |
| Label tier | `tier: web` present sur tous les pods, utilise par le Service | Conforme |
| ConfigMap monte | Volume `nginx-config` sur `/etc/nginx/conf.d/default.conf` | Conforme |

### Tests fonctionnels

| Critere | Statut |
|---------|--------|
| Round robin (au moins 2 hostnames sur 10 requetes) | En attente (lab) |
| Failover (service disponible apres suppression d'un pod) | En attente (lab) |
| Recuperation (ReplicaSet recree un pod en < 60 s) | En attente (lab) |
| Accessibilite (service joignable via IP ou port-forward) | En attente (lab) |
