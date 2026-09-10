# Site Web Statique Dockerisé avec Load Balancing Kubernetes

Déploiement de deux sites web statiques (Site A et Site B) sur un cluster Kubernetes,
avec un Service de type `LoadBalancer` assurant la répartition de charge en mode
**Round Robin**. Chaque site est déployé sur 2 replicas, soit un total de 4 pods
derrière un unique point d'entrée HTTP. Le projet démontre la répartition de charge,
le failover et la récupération automatique des pods.

---

## Architecture

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
        +-------+-------+         +-------+-------+
                |                         |
        +-------+-------+         +-------+-------+
        | Pod A-1       |         | Pod B-1       |
        | Pod A-2       |         | Pod B-2       |
        +---------------+         +---------------+
```

### Composants

| Composant | Role |
|-----------|------|
| **Site A** | Site statique a theme bleu (`#2196F3`), affichant « SITE A » avec hostname dynamique et horodatage |
| **Site B** | Site statique a theme vert (`#4CAF50`), affichant « SITE B » avec hostname dynamique et horodatage |
| **LoadBalancer** | Service Kubernetes de type `LoadBalancer` avec `sessionAffinity: None` pour le round robin |
| **ConfigMap** | Configuration Nginx partagee montee en volume dans chaque pod |
| **Deployments** | Deux Deployments (un par site) avec 2 replicas chacun, liveness et readiness probes |

---

## Pre requis

| Composant | Version minimale | Usage |
|-----------|------------------|-------|
| Docker | 20.10+ | Construction des images |
| kubectl | 1.25+ | Interaction avec le cluster Kubernetes |
| Cluster Kubernetes | 1.25+ | Minikube, K3s ou Kind |
| curl | 7.0+ | Requetes HTTP pour les tests |
| Bash | 4.0+ | Execution des scripts |

---

## Installation rapide

### 1. Cloner le depot

```bash
git clone https://github.com/yugmerabtene/site-web-statique-k8s.git
cd site-web-statique-k8s
```

### 2. Construire les images Docker

```bash
./scripts/build.sh
```

Ce script construit les images `site-a:1.0` et `site-b:1.0` a partir des Dockerfiles
dans `docker/`. Il verifie automatiquement que chaque image fait moins de 50 Mo.

### 3. Deployer sur Kubernetes

```bash
./scripts/deploy.sh
```

Ce script applique les manifestes Kubernetes dans l'ordre (ConfigMap, Deployments,
Service LoadBalancer), attend la convergence des pods, et affiche l'adresse du
LoadBalancer. En environnement local sans IP externe, il fournit les commandes
d'acces en port-forward.

### 4. Tester le round robin et le failover

```bash
./scripts/test-loadbalancer.sh
```

Ce script execute trois tests :
- **Test 1 (Round Robin)** : envoie 10 requetes et verifie que au moins 2 hostnames
  distincts apparaissent.
- **Test 2 (Failover)** : supprime un pod et verifie que le service continue de
  fonctionner.
- **Test 3 (Recuperation)** : verifie que le ReplicaSet recree un nouveau pod en
  moins de 60 secondes.

### Acces en environnement local

Si aucune IP externe n'est assignee au LoadBalancer (cas de Minikube, K3s ou Kind) :

```bash
# Option 1 : port-forward
kubectl port-forward service/site-loadbalancer 8080:80 -n default
curl http://localhost:8080

# Option 2 : Minikube
minikube service site-loadbalancer -n default --url
```

---

## Structure du projet

```
.
├── docker/                           Configuration Docker et Nginx
│   ├── Dockerfile.site-a             Dockerfile du Site A (nginx:alpine)
│   ├── Dockerfile.site-b             Dockerfile du Site B (nginx:alpine)
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
├── CAHIER_DES_CHARGES.md             Cahier des charges du projet
├── rapport_tests.md                  Rapport de tests
├── README.md                         Ce fichier
└── .env                              Variables d'environnement (gitignore)
```

---

## Configuration

### Ports

| Composant | Port | Protocole |
|-----------|------|-----------|
| Conteneur Nginx | 8080 | TCP |
| Service Kubernetes | 80 | TCP |
| TargetPort (Service -> Pod) | 8080 | TCP |

### Namespace et labels

| Element | Valeur |
|---------|--------|
| Namespace | `default` |
| Label app (Site A) | `app: site-a` |
| Label app (Site B) | `app: site-b` |
| Label tier (commun) | `tier: web` |
| Selecteur du Service | `tier: web` |

### Images Docker

| Image | Base | Taille cible | Utilisateur |
|-------|------|-------------|-------------|
| `site-a:1.0` | `nginx:alpine` | < 50 Mo | `appuser` (UID 1001) |
| `site-b:1.0` | `nginx:alpine` | < 50 Mo | `appuser` (UID 1001) |

### Ressources Kubernetes

| Ressource | Limite |
|-----------|--------|
| CPU | 100m par conteneur |
| Memoire | 64Mi par conteneur |

### Probes

| Probe | Type | Chemin | Port | Periode | Seuil d'echec |
|-------|------|--------|------|---------|----------------|
| Liveness | HTTP GET | `/` | 8080 | 10 s | 3 |
| Readiness | HTTP GET | `/` | 8080 | 5 s | 3 |

---

## Depannnage

### Images Docker non trouvees

**Symptome** : le script `deploy.sh` affiche `ERREUR: L'image 'site-a:1.0' n'existe pas localement`.

**Solution** : executer d'abord la construction des images :

```bash
./scripts/build.sh
```

### Pods en CrashLoopBackOff

**Symptome** : `kubectl get pods` affiche `CrashLoopBackOff` ou `Error`.

**Diagnostic** :

```bash
kubectl logs -l app=site-a -n default --tail=50
kubectl logs -l app=site-b -n default --tail=50
```

**Causes courantes** :
- Le port expose dans le Dockerfile (8080) ne correspond pas au containerPort du Deployment.
- Le fichier `nginx.conf` est absent ou mal configure.
- L'utilisateur non-root (UID 1001) n'a pas les droits de lecture sur les fichiers statiques.

### Service LoadBalancer sans IP externe

**Symptome** : `kubectl get service site-loadbalancer` affiche `<pending>` dans la colonne `EXTERNAL-IP`.

**Cause** : l'environnement local (Minikube, Kind, K3s) ne fournit pas de LoadBalancer
natif.

**Solution** : utiliser le port-forward :

```bash
kubectl port-forward service/site-loadbalancer 8080:80 -n default
curl http://localhost:8080
```

Pour Minikube, activer l'add-on metallb ou utiliser `minikube tunnel` dans un terminal
separe.

### Le round robin ne fonctionne pas

**Diagnostic** : verifier que `sessionAffinity: None` est bien present dans le Service :

```bash
kubectl get service site-loadbalancer -n default -o yaml | grep sessionAffinity
```

Si le probleme persiste, verifier que le label `tier: web` est present sur tous les pods :

```bash
kubectl get pods -n default -l tier=web -o wide
```

---

## Auteurs

- **yugmerabtene** -- developpement, deploiement et documentation

## Licence

Ce projet est distribue sous la licence MIT. Consultez le fichier `LICENSE` pour
plus de details.
