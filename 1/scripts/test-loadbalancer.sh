#!/usr/bin/env bash
# =============================================================================
# test-loadbalancer.sh — Tests du round robin, failover et récupération.
# Valide que la distribution de charge fonctionne correctement sur le
# LoadBalancer Kubernetes exposé par le Service site-loadbalancer.
# =============================================================================

set -euo pipefail

# --- Variables -------------------------------------------------------------- #

NAMESPACE="default"
SERVICE_NAME="site-loadbalancer"
TOTAL_REQUESTS=10
PORT_FORWARD_LOCAL_PORT=18080
PORT_FORWARD_REMOTE_PORT=80

# Compteurs de résultats
PASS_COUNT=0
FAIL_COUNT=0

# --- Fonctions utilitaires ------------------------------------------------- #

# Afficher un résultat PASS ou FAIL
# Arguments: nom_du_test "PASS" ou "FAIL" [message_detaille]
result() {
    local test_name="$1"
    local status="$2"
    local detail="${3:-}"

    if [ "$status" = "PASS" ]; then
        echo "  PASS: ${test_name}"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "  FAIL: ${test_name}"
        if [ -n "$detail" ]; then
            echo "        ${detail}"
        fi
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# Déterminer l'URL d'accès au LoadBalancer
# Gere Minikube, K3s (IP externe), et fallback port-forward.
detect_service_url() {
    local url=""

    # Stratégie 1 : IP externe ou hostname assigné au service
    local lb_ip lb_hostname
    lb_ip=$(kubectl get service/"${SERVICE_NAME}" -n "${NAMESPACE}" \
        -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
    lb_hostname=$(kubectl get service/"${SERVICE_NAME}" -n "${NAMESPACE}" \
        -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)

    if [ -n "${lb_hostname}" ]; then
        url="http://${lb_hostname}"
        echo "$url"
        return 0
    fi
    if [ -n "${lb_ip}" ]; then
        url="http://${lb_ip}"
        echo "$url"
        return 0
    fi

    # Stratégie 2 : minikube (si disponible)
    if command -v minikube &>/dev/null && minikube status &>/dev/null 2>&1; then
        local minikube_url
        minikube_url=$(minikube service "${SERVICE_NAME}" -n "${NAMESPACE}" --url 2>/dev/null || true)
        if [ -n "${minikube_url}" ]; then
            echo "$minikube_url"
            return 0
        fi
    fi

    # Stratégie 3 : fallback avec port-forward
    echo ""
    return 1
}

# Extraire le hostname de la réponse HTML
# Le HTML contient : <span ... id="hostname">POD_NAME</span>
# Le entrypoint.sh remplace {{HOSTNAME}} par $HOSTNAME (nom du pod)
extract_hostname() {
    local response="$1"
    echo "$response" | grep -oE 'id="hostname">[^<]+' | sed 's/id="hostname">//' || true
}

# --- Démarrage des tests --------------------------------------------------- #

echo "==============================================="
echo " Tests du Load Balancer Kubernetes"
echo "==============================================="
echo ""

# --- Détection de l'URL du service ----------------------------------------- #

echo "--- Détection de l'URL du service ---"

LB_URL=""
USE_PORT_FORWARD=false

detected_url=$(detect_service_url) || true

if [ -n "$detected_url" ]; then
    LB_URL="$detected_url"
    echo "URL detectee: ${LB_URL}"
else
    echo "Aucune IP externe disponible. Démarrage du port-forward..."
    USE_PORT_FORWARD=true
    LB_URL="http://127.0.0.1:${PORT_FORWARD_LOCAL_PORT}"

    # Lancer le port-forward en arrière-plan
    kubectl port-forward "service/${SERVICE_NAME}" \
        "${PORT_FORWARD_LOCAL_PORT}:${PORT_FORWARD_REMOTE_PORT}" \
        -n "${NAMESPACE}" &>/dev/null &
    PF_PID=$!
    # Enregistrer le PID pour le nettoyage à la fin
    trap "kill ${PF_PID} 2>/dev/null || true" EXIT

    echo "Port-forward demarre (PID: ${PF_PID}), URL: ${LB_URL}"
    echo "Attente de la stabilisation du port-forward..."
    sleep 3
fi

# Vérifier que le service est joignable
echo ""
echo "--- Vérification de l'accessibilité du service ---"
if curl -sf --max-time 5 "${LB_URL}" &>/dev/null; then
    result "Service accessible via ${LB_URL}" "PASS"
else
    result "Service accessible via ${LB_URL}" "FAIL" "Impossible d'atteindre le service"
    echo ""
    echo "Arrêt des tests."
    exit 1
fi

# ========================================================================== #
# TEST 1 : Round Robin                                                       #
# ========================================================================== #

echo ""
echo "==============================================="
echo " TEST 1 — Round Robin (${TOTAL_REQUESTS} requetes)"
echo "==============================================="
echo ""

declare -A hostname_counts
unique_hostnames=()

for i in $(seq 1 ${TOTAL_REQUESTS}); do
    response=$(curl -sf --max-time 5 "${LB_URL}" 2>/dev/null || true)
    if [ -z "$response" ]; then
        echo "  Requête ${i}: ERREUR (pas de réponse)"
        continue
    fi

    hostname=$(extract_hostname "$response")
    if [ -z "$hostname" ]; then
        echo "  Requête ${i}: hostname non détecté dans la réponse"
        hostname="inconnu"
    fi
    echo "  Requête ${i}: hostname = ${hostname}"

    # Compter les occurrences de chaque hostname
    if [ -z "${hostname_counts[$hostname]+x}" ]; then
        hostname_counts[$hostname]=1
        unique_hostnames+=("$hostname")
    else
        hostname_counts[$hostname]=$(( ${hostname_counts[$hostname]} + 1 ))
    fi
done

echo ""
echo "Résumé du round robin :"
echo "  Hostnames uniques détectés : ${#unique_hostnames[@]}"
for h in "${unique_hostnames[@]}"; do
    echo "    - ${h} : ${hostname_counts[$h]} fois"
done

echo ""

# Vérifier qu'au moins 2 hostnames différents sont apparus
if [ "${#unique_hostnames[@]}" -ge 2 ]; then
    result "Au moins 2 hostnames différents détectés (preuve du round robin)" "PASS"
else
    result "Au moins 2 hostnames différents détectés (preuve du round robin)" "FAIL" \
        "Un seul hostname detecte: ${unique_hostnames[0]:-aucun}. Le round robin ne fonctionne pas."
fi

# ========================================================================== #
# TEST 2 : Failover                                                          #
# ========================================================================== #

echo ""
echo "==============================================="
echo " TEST 2 — Failover"
echo "==============================================="
echo ""

# Sélectionner un pod à supprimer (préférer un pod Site A)
echo "Sélection du pod à supprimer..."
TARGET_POD=$(kubectl get pods -n "${NAMESPACE}" -l app=site-a \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

if [ -z "$TARGET_POD" ]; then
    # Fallback : prendre un pod du tier web
    TARGET_POD=$(kubectl get pods -n "${NAMESPACE}" -l tier=web \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
fi

if [ -z "$TARGET_POD" ]; then
    result "Suppression du pod" "FAIL" "Aucun pod disponible pour le test de failover"
else
    echo "  Pod sélectionné pour suppression : ${TARGET_POD}"
    echo ""

    # Compter les pods avant suppression
    pods_before=$(kubectl get pods -n "${NAMESPACE}" -l tier=web --no-headers 2>/dev/null | wc -l)
    echo "  Pods actifs avant suppression : ${pods_before}"

    # Supprimer le pod
    echo "  Suppression du pod ${TARGET_POD}..."
    kubectl delete pod "${TARGET_POD}" -n "${NAMESPACE}" --grace-period=0 --force 2>/dev/null || \
        kubectl delete pod "${TARGET_POD}" -n "${NAMESPACE}" 2>/dev/null

    # Attendre brièvement que le pod soit en cours de terminaison
    sleep 2

    # Envoyer des requêtes pour vérifier que le service continue de fonctionner
    echo ""
    echo "  Envoi de requêtes après suppression du pod..."
    failover_success=true
    for i in $(seq 1 5); do
        http_code=$(curl -sf -o /dev/null -w '%{http_code}' --max-time 5 "${LB_URL}" 2>/dev/null || echo "000")
        echo "    Requête ${i}: code HTTP = ${http_code}"
        if [ "$http_code" = "000" ] || [[ "$http_code" =~ ^5 ]]; then
            failover_success=false
        fi
    done

    echo ""
    if [ "$failover_success" = true ]; then
        result "Le service continue de fonctionner après suppression d'un pod" "PASS"
    else
        result "Le service continue de fonctionner après suppression d'un pod" "FAIL" \
            "Des erreurs détectées pendant le failover"
    fi
fi

# ========================================================================== #
# TEST 3 : Récupération (pod recréé par le ReplicaSet)                       #
# ========================================================================== #

echo ""
echo "==============================================="
echo " TEST 3 — Récupération du pod"
echo "==============================================="
echo ""

if [ -n "$TARGET_POD" ]; then
    echo "  Attente de la re-création des pods (timeout 60s)..."

    # Attendre que le nombre de pods revienne à la valeur attendue
    recovery_success=false
    for i in $(seq 1 12); do
        sleep 5
        pods_now=$(kubectl get pods -n "${NAMESPACE}" -l tier=web \
            --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
        echo "    Vérification ${i}/12 : pods Running = ${pods_now} (attendu: ${pods_before})"

        if [ "$pods_now" -ge "$pods_before" ]; then
            recovery_success=true
            break
        fi
    done

    echo ""
    if [ "$recovery_success" = true ]; then
        result "Le ReplicaSet a recréé un nouveau pod pour maintenir les replicas" "PASS"
    else
        result "Le ReplicaSet a recréé un nouveau pod pour maintenir les replicas" "FAIL" \
            "Le nombre de pods Running (${pods_now}) n'a pas atteint ${pods_before} après 60s"
    fi
else
    result "Récupération du pod" "FAIL" "Pod non sélectionné, test ignoré"
fi

# --- Affichage final du statut des pods ------------------------------------ #

echo ""
echo "=== Statut final des pods ==="
kubectl get pods -n "${NAMESPACE}" -l tier=web -o wide

# --- Résumé des tests ------------------------------------------------------ #

echo ""
echo "==============================================="
echo " Résumé des tests"
echo "==============================================="
echo "  PASS: ${PASS_COUNT}"
echo "  FAIL: ${FAIL_COUNT}"
echo "  Total: $((PASS_COUNT + FAIL_COUNT))"
echo ""

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "RESULTAT: ÉCHEC — ${FAIL_COUNT} test(s) ont échoué."
    exit 1
else
    echo "RESULTAT: SUCCÈS — Tous les tests sont passés."
    exit 0
fi
