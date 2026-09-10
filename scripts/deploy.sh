#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Deploiement des sites A et B sur Kubernetes.
# Applique les manifestes dans l'ordre : ConfigMap, Deployments, Service.
# =============================================================================

set -euo pipefail

# --- Variables -------------------------------------------------------------- #

IMAGE_A="site-a:1.0"
IMAGE_B="site-b:1.0"
NAMESPACE="default"
MANIFEST_DIR="k8s"

CONFIGMAP="${MANIFEST_DIR}/configmap.yaml"
DEPLOYMENT_A="${MANIFEST_DIR}/deployment-site-a.yaml"
DEPLOYMENT_B="${MANIFEST_DIR}/deployment-site-b.yaml"
SERVICE_LB="${MANIFEST_DIR}/service-loadbalancer.yaml"

# --- Verification de kubectl et du cluster --------------------------------- #

echo "=== Verification de kubectl ==="
if ! command -v kubectl &>/dev/null; then
    echo "ERREUR: kubectl n'est pas installable ou absent du PATH."
    exit 1
fi
echo "OK: kubectl disponible ($(kubectl version --client --short 2>/dev/null || kubectl version --client 2>/dev/null | head -1))"

echo ""
echo "=== Verification de l'acces au cluster ==="
if ! kubectl cluster-info &>/dev/null; then
    echo "ERREUR: Impossible de joindre le cluster Kubernetes."
    echo "        Verifiez que votre contexte kubectl est correctement configure."
    exit 1
fi
echo "OK: Cluster accessible"

# --- Verification de la presence des images locales ------------------------- #

echo ""
echo "=== Verification des images Docker locales ==="
for image in "${IMAGE_A}" "${IMAGE_B}"; do
    if ! docker image inspect "${image}" &>/dev/null; then
        echo "ERREUR: L'image '${image}' n'existe pas localement."
        echo "        Lancez d'abord ./scripts/build.sh pour construire les images."
        exit 1
    fi
    echo "OK: Image '${image}' presente"
done

# --- Application des manifestes dans l'ordre -------------------------------- #

echo ""
echo "=== Application des manifestes ==="

echo "1/4 Application du ConfigMap..."
kubectl apply -f "${CONFIGMAP}" -n "${NAMESPACE}"

echo "2/4 Application du Deployment Site A..."
kubectl apply -f "${DEPLOYMENT_A}" -n "${NAMESPACE}"

echo "3/4 Application du Deployment Site B..."
kubectl apply -f "${DEPLOYMENT_B}" -n "${NAMESPACE}"

echo "4/4 Application du Service LoadBalancer..."
kubectl apply -f "${SERVICE_LB}" -n "${NAMESPACE}"

# --- Attente du deploiement ------------------------------------------------ #

echo ""
echo "=== Attente de la mise a jour des Deployments ==="

echo "Site A..."
kubectl rollout status deployment/site-a -n "${NAMESPACE}" --timeout=120s

echo "Site B..."
kubectl rollout status deployment/site-b -n "${NAMESPACE}" --timeout=120s

# --- Affichage du statut --------------------------------------------------- #

echo ""
echo "=== Statut des Pods ==="
kubectl get pods -n "${NAMESPACE}" -l tier=web -o wide

echo ""
echo "=== Statut du Service LoadBalancer ==="
kubectl get service/site-loadbalancer -n "${NAMESPACE}"

# --- Recuperation et affichage de l'adresse du LoadBalancer ----------------- #

echo ""
echo "=== Adresse du LoadBalancer ==="

# Attendre brievement que l'IP externe soit assignee (timeout 60s)
LB_IP=""
for i in $(seq 1 12); do
    LB_IP=$(kubectl get service/site-loadbalancer -n "${NAMESPACE}" \
        -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
    LB_HOST=$(kubectl get service/site-loadbalancer -n "${NAMESPACE}" \
        -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)

    if [ -n "${LB_IP}" ] || [ -n "${LB_HOST}" ]; then
        break
    fi
    echo "  En attente de l'assignation de l'adresse IP externe... (${i}/12)"
    sleep 5
done

if [ -n "${LB_HOST}" ]; then
    echo "URL: http://${LB_HOST}"
elif [ -n "${LB_IP}" ]; then
    echo "URL: http://${LB_IP}"
else
    echo "Aucune IP externe assignee (typique en environnement local)."
    echo ""
    echo "Pour acceder au service en environnement local, utilisez :"
    echo "  Minikube :  minikube service site-loadbalancer -n ${NAMESPACE} --url"
    echo "  Port-Fwd :  kubectl port-forward service/site-loadbalancer 8080:80 -n ${NAMESPACE}"
    echo "              curl http://localhost:8080"
fi

echo ""
echo "=== Deploiement termine avec succes ==="
