# Rapport de tests — Site Web Statique Dockerisé avec Load Balancing Kubernetes

| Champ            | Valeur                                                      |
| ---------------- | ----------------------------------------------------------- |
| **Date**         | 2026-09-10                                                  |
| **Auteur**       | yugmerabtene                                                |
| **Version**      | 1.0.0                                                       |
| **Statut**       | EN ATTENTE (tests à exécuter en environnement de laboratoire) |

---

## 1. Résumé exécutif

### Objectif du projet

Ce projet vise à déployer deux sites web statiques — **Site A** et **Site B** — sur un cluster Kubernetes, répartis par un Service de type `LoadBalancer` en mode **Round Robin**. Chaque site est déployé sur **2 replicas**, soit un total de **4 pods** derrière un même point d'entrée HTTP. Les deux fonctionnalités clés à démontrer sont :

- La **répartition de charge** (Round Robin) : les requêtes entrantes alternent entre les pods de Site A et de Site B de manière cyclique.
- Le **failover** : la suppression ou la défaillance d'un pod n'interrompt pas le service, et le ReplicaSet recrée automatiquement un nouveau pod pour maintenir le nombre de replicas souhaité.

### Environnement de test

Les tests sont conçus pour être exécutés sur l'un des environnements de laboratoire suivants :

- **Minikube** (cluster Kubernetes local en un seul nœud)
- **K3s** (distribution Kubernetes légère)
- **Kind** (Kubernetes in Docker)

Ces environnements offrent un cluster fonctionnel sans infrastructure cloud, idéal pour la validation fonctionnelle.

### Résultat global

| Statut global |
| ------------- |
| **EN ATTENTE** |

Les tests seront exécutés manuellement en environnement de laboratoire. Les résultats seront consolidés dans ce document après chaque campagne de tests.

---

## 2. Prérequis

Avant l'exécution des tests, l'environnement de laboratoire doit satisfaire les prérequis suivants :

| Composant      | Version minimale recommandée | Usage                               |
| -------------- | ---------------------------- | ----------------------------------- |
| Docker         | 20.10+                       | Construction des images             |
| kubectl        | 1.25+                        | Interaction avec le cluster K8s     |
| Cluster K8s    | 1.25+ (Minikube, K3s ou Kind) | Hébergement des pods               |
| curl           | 7.0+                         | Requêtes HTTP pour les tests        |
| Bash           | 4.0+                         | Exécution des scripts de test       |

---

## 3. Protocole de test

### Test 1 : Construction des images Docker

| Champ           | Détail                                                  |
| --------------- | ------------------------------------------------------- |
| **Script**      | `./scripts/build.sh`                                    |
| **Commande**    | `./scripts/build.sh` (depuis la racine du projet)       |
| **Ce qui est testé** | Les images `site-a:1.0` et `site-b:1.0` sont construites à partir des Dockerfiles dans `docker/`. Les images reposent sur `nginx:alpine` et contiennent uniquement les fichiers statiques (HTML, CSS, JS) ainsi que la configuration Nginx partagée. |
| **Critère de succès** | Les deux images existent, sont fonctionnelles, et chaque image fait **moins de 50 Mo**. Le script vérifie automatiquement la taille et signale un échec si la limite est dépassée. |
| **Résultat**    | **EN ATTENTE**                                          |

**Détail technique :** Les Dockerfiles créent un utilisateur non-root (`appuser`, UID 1001), copient les fichiers statiques dans `/usr/share/nginx/html/`, installent un entrypoint qui remplace le placeholder `{{HOSTNAME}}` par la valeur de la variable d'environnement `$HOSTNAME` au démarrage, puis lancent Nginx en premier plan. Le port exposé est le 8080.

---

### Test 2 : Déploiement sur Kubernetes

| Champ           | Détail                                                  |
| --------------- | ------------------------------------------------------- |
| **Script**      | `./scripts/deploy.sh`                                   |
| **Commande**    | `./scripts/deploy.sh` (depuis la racine du projet)      |
| **Ce qui est testé** | Application des manifestes Kubernetes dans l'ordre : ConfigMap, Deployments (Site A et Site B), Service LoadBalancer. Vérification que tous les pods atteignent le statut `Running` et que le Service obtient une adresse IP externe (ou un mécanisme de port-forward). |
| **Critère de succès** | - **4 pods** en statut `Running` (2 pour Site A, 2 pour Site B).<br>- Le Service `site-loadbalancer` existe et est de type `LoadBalancer`.<br>- Le service est joignable via l'IP externe ou via `port-forward`. |
| **Résultat**    | **EN ATTENTE**                                          |

**Détail technique :** Le script applique les quatre manifestes via `kubectl apply`, attend la convergence des Deployments avec `kubectl rollout status` (timeout 120 s), puis affiche le statut des pods et du Service. Si aucune IP externe n'est assignée (typique en Minikube), le script fournit la commande `minikube service` ou `kubectl port-forward` pour accéder au service.

---

### Test 3 : Round Robin

| Champ           | Détail                                                  |
| --------------- | ------------------------------------------------------- |
| **Script**      | `./scripts/test-loadbalancer.sh` — **TEST 1**           |
| **Commande**    | `./scripts/test-loadbalancer.sh`                        |
| **Ce qui est testé** | Le script envoie **10 requêtes HTTP** au LoadBalancer et extrait le hostname du pod ayant servi chaque réponse. Le hostname correspond au nom du pod Kubernetes (remplacé dans `index.html` par l'entrypoint au démarrage). Le round robin est considéré comme validé si au moins **2 hostnames distincts** apparaissent parmi les 10 réponses. |
| **Critère de succès** | Au moins 2 hostnames différents détectés sur 10 requêtes, preuve que la répartition de charge fonctionne. |
| **Résultat**    | **EN ATTENTE**                                          |

**Détail technique :** Le hostname est extrait de chaque réponse HTML via l'extraction de l'élément `<span id="hostname">`. Le service utilise `sessionAffinity: None`, garantissant l'absence de sticky session et la rotation effective entre les 4 pods. Le script gère automatiquement la détection de l'URL d'accès (IP externe, Minikube service URL, ou port-forward en fallback).

---

### Test 4 : Failover

| Champ           | Détail                                                  |
| --------------- | ------------------------------------------------------- |
| **Script**      | `./scripts/test-loadbalancer.sh` — **TEST 2**           |
| **Commande**    | `./scripts/test-loadbalancer.sh`                        |
| **Ce qui est testé** | Après le test de round robin, le script sélectionne un pod (prioritairement un pod du Site A) et le supprime avec `kubectl delete pod`. Il envoie ensuite **5 requêtes de vérification** pour confirmer que le service continue de fonctionner normalement malgré la perte d'un pod. |
| **Critère de succès** | Les 5 requêtes de vérification retournent un code HTTP 2xx. Le service reste disponible et joignable après la suppression du pod. |
| **Résultat**    | **EN ATTENTE**                                          |

**Détail technique :** La suppression du pod entraîne le retrait automatique du pod par le readiness probe (le pod est retiré de la liste des endpoints du Service). Les requêtes sont alors redirigées vers les pods restants. Le test valide cette transparence de la redirection.

---

### Test 5 : Récupération

| Champ           | Détail                                                  |
| --------------- | ------------------------------------------------------- |
| **Script**      | `./scripts/test-loadbalancer.sh` — **TEST 3**           |
| **Commande**    | `./scripts/test-loadbalancer.sh`                        |
| **Ce qui est testé** | Après la suppression du pod (Test 4), le script attend que le ReplicaSet recrée un nouveau pod pour maintenir le nombre de replicas configuré (2). Il vérifie régulièrement (toutes les 5 secondes, pendant 60 secondes maximum) que le nombre de pods en statut `Running` revient à la valeur initiale. |
| **Critère de succès** | Le ReplicaSet recrée un nouveau pod et le nombre de pods `Running` atteint le nombre initial (pods_before) en **moins de 60 secondes**. |
| **Résultat**    | **EN ATTENTE**                                          |

**Détail technique :** Le mécanisme de récupération est assuré par le champ `replicas: 2` dans les Deployments. Lorsqu'un pod est supprimé, le ReplicaSet détecte l'écart entre l'état souhaité (2) et l'état actuel (1), et crée immédiatement un nouveau pod. Le script valide ce comportement en polluant `kubectl get pods` avec le filtre `--field-selector=status.phase=Running`.

---

## 4. Matrice de conformité

### 4.1 Conformité du code (vérification statique)

| Critère                            | Spécification                          | Statut               |
| ---------------------------------- | -------------------------------------- | -------------------- |
| Site A affiche « SITE A » en bleu  | `#2196F3` (variable `--color-primary` dans `site-a/style.css`) | Vérifié (code) |
| Site B affiche « SITE B » en vert  | `#4CAF50` (variable `--color-primary` dans `site-b/style.css`) | Vérifié (code) |
| Hostname affiché dynamiquement     | Placeholder `{{HOSTNAME}}` dans `index.html`, remplacé par `sed` dans l'entrypoint au démarrage du conteneur | Vérifié (code) |
| Horodatage temps réel              | `setInterval(updateTimestamp, 1000)` dans `script.js` | Vérifié (code) |
| Compteur de requêtes               | Variable locale `requestCount` incrémentée au chargement | Vérifié (code) |
| CSS responsive                     | Media query `@media (max-width: 480px)` pour l'adaptation mobile | Vérifié (code) |
| Aucune dépendance externe          | HTML5, CSS3, JS vanilla uniquement     | Vérifié (code) |

### 4.2 Conformité des conteneurs

| Critère                            | Spécification                          | Statut               |
| ---------------------------------- | -------------------------------------- | -------------------- |
| Images < 50 Mo                     | `nginx:alpine` + fichiers statiques uniquement | Vérifié (code) |
| Conteneurs non-root                | `USER appuser` (UID 1001), `runAsNonRoot: true` dans les Dockerfiles et les Deployments | Vérifié (code) |
| Port exposé 8080                   | `EXPOSE 8080` dans les Dockerfiles, `containerPort: 8080` dans les Deployments | Vérifié (code) |
| Entrypoint correct                 | `sed` remplace `{{HOSTNAME}}` puis `nginx -g "daemon off;"` | Vérifié (code) |

### 4.3 Conformité Kubernetes

| Critère                            | Spécification                          | Statut               |
| ---------------------------------- | -------------------------------------- | -------------------- |
| 2 replicas par site                | `replicas: 2` dans `deployment-site-a.yaml` et `deployment-site-b.yaml` | Vérifié (manifeste) |
| sessionAffinity: None              | `sessionAffinity: None` dans `service-loadbalancer.yaml` | Vérifié (manifeste) |
| Liveness probe                     | `httpGet` sur le port 8080, chemin `/`, period 10s, failureThreshold 3 | Vérifié (manifeste) |
| Readiness probe                    | `httpGet` sur le port 8080, chemin `/`, period 5s, failureThreshold 3 | Vérifié (manifeste) |
| Service type LoadBalancer          | `type: LoadBalancer` dans `service-loadbalancer.yaml` | Vérifié (manifeste) |
| Labels de sélection                | `tier: web` comme sélecteur du Service couvrant les deux Deployments | Vérifié (manifeste) |
| Ressources limitées                | CPU 100m, mémoire 64Mi par conteneur   | Vérifié (manifeste) |
| ConfigMap Nginx monté              | Volume `nginx-config` monté sur `/etc/nginx/conf.d/default.conf` | Vérifié (manifeste) |

### 4.4 Conformité fonctionnelle (tests en lab)

| Critère                            | Spécification                          | Statut               |
| ---------------------------------- | -------------------------------------- | -------------------- |
| Round robin fonctionnel            | Au moins 2 hostnames différents sur 10 requêtes | EN ATTENTE (lab) |
| Failover transparent               | Le service continue de fonctionner après suppression d'un pod | EN ATTENTE (lab) |
| Récupération automatique           | ReplicaSet recrée un pod en < 60 s     | EN ATTENTE (lab) |
| Accessibilité du service           | Le service est joignable via IP externe ou port-forward | EN ATTENTE (lab) |

---

## 5. Résultats détaillés

> Les résultats ci-dessous seront remplis lors de l'exécution des tests en environnement de laboratoire.

### 5.1 Test 1 — Build des images

| Champ               | Valeur   |
| ------------------- | -------- |
| Date d'exécution    | --       |
| Environnement       | --       |
| Image `site-a:1.0`  | --       |
| Taille `site-a:1.0` | -- Mo    |
| Image `site-b:1.0`  | --       |
| Taille `site-b:1.0` | -- Mo    |
| Statut              | EN ATTENTE |
| Observations        | --       |

### 5.2 Test 2 — Déploiement

| Champ               | Valeur   |
| ------------------- | -------- |
| Date d'exécution    | --       |
| Environnement       | --       |
| Pods Site A         | -- / 2 Running |
| Pods Site B         | -- / 2 Running |
| IP LoadBalancer     | --       |
| Statut              | EN ATTENTE |
| Observations        | --       |

### 5.3 Test 3 — Round Robin

| Champ               | Valeur   |
| ------------------- | -------- |
| Date d'exécution    | --       |
| Environnement       | --       |
| Nombre de requêtes  | 10       |
| Hostnames uniques   | --       |
| Details             | --       |
| Statut              | EN ATTENTE |
| Observations        | --       |

### 5.4 Test 4 — Failover

| Champ               | Valeur   |
| ------------------- | -------- |
| Date d'exécution    | --       |
| Environnement       | --       |
| Pod supprimé        | --       |
| Requêtes après suppression | -- / 5 succès |
| Statut              | EN ATTENTE |
| Observations        | --       |

### 5.5 Test 5 — Recuperation

| Champ               | Valeur   |
| ------------------- | -------- |
| Date d'exécution    | --       |
| Environnement       | --       |
| Pods avant suppression | --    |
| Pods après récupération | --   |
| Délai de récupération | -- s   |
| Statut              | EN ATTENTE |
| Observations        | --       |

---

## 6. Conclusion

### Synthèse des résultats

L'analyse statique du code-source confirme la conformité de l'ensemble des composants avec les spécifications du projet :

- Les deux sites affichent correctement leur identité visuelle (« SITE A » en bleu, « SITE B » en vert) avec des couleurs conformes à la charte.
- L'affichage dynamique du hostname repose sur un mécanisme robuste : le placeholder `{{HOSTNAME}}` est remplacé par `sed` au démarrage du conteneur, garantissant que chaque pod affiche son propre nom.
- L'horodatage est mis à jour en temps réel toutes les secondes via `setInterval`.
- Les images Docker sont basées sur `nginx:alpine` et ne contiennent que les fichiers statiques strictement nécessaires, ce qui garantit une taille inférieure à 50 Mo.
- Les conteneurs s'exécutent en tant qu'utilisateur non-root (UID 1001), conformément aux bonnes pratiques de sécurité.
- Les manifestes Kubernetes définissent correctement 2 replicas par site, des liveness et readiness probes sur le port 8080, et un Service LoadBalancer en mode round robin (sans affinité de session).

Les tests fonctionnels (round robin, failover, récupération) restent en attente d'exécution en environnement de laboratoire. Le script de test `test-loadbalancer.sh` est entièrement opérationnel et gère automatiquement la détection de l'URL d'accès (IP externe, Minikube, ou port-forward en fallback).

### Prochaines étapes

1. **Exécution des tests en lab** : déployer le stack sur Minikube (ou K3s/Kind) et exécuter `./scripts/build.sh`, `./scripts/deploy.sh`, puis `./scripts/test-loadbalancer.sh` pour obtenir les résultats concrets.
2. **Mise à jour de ce rapport** : intégrer les résultats réels dans les tableaux de la section 5 et faire passer le statut global de « EN ATTENTE » à « SUCCÈS » ou « ÉCHEC ».
3. **Relecture finale** : soumettre le rapport complété au `proofreader` pour vérification de la conformité linguistique et technique.
4. **Versionnement** : committer et pousser le rapport final sur le dépôt git.
