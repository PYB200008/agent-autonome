#!/usr/bin/env bash
# =============================================================================
# build.sh — Construction des images Docker pour Site A et Site B.
# S'exécuter depuis la racine du projet : docker build -f docker/Dockerfile.site-<x> .
# =============================================================================

set -euo pipefail

# --- Variables -------------------------------------------------------------- #

IMAGE_A="site-a:1.0"
IMAGE_B="site-b:1.0"
DOCKERFILE_A="docker/Dockerfile.site-a"
DOCKERFILE_B="docker/Dockerfile.site-b"
BUILD_CONTEXT="."
SIZE_LIMIT_MB=50

# --- Fonction : extraire la taille d'une image Docker (en Mo) --------------- #

get_image_size_mb() {
    local image="$1"
    # docker images --format '{{.Size}}' renvoie une chaine du type "29.6MB"
    local size_str
    size_str=$(docker images --format '{{.Size}}' "$image" | head -1)
    # Convertir en nombre flottant (supprimer le suffixe MB/Mo)
    echo "$size_str" | sed 's/[^0-9.]//g'
}

# --- Construction de l'image Site A ----------------------------------------- #

echo "=== Construction de l'image ${IMAGE_A} ==="
docker build -f "${DOCKERFILE_A}" -t "${IMAGE_A}" "${BUILD_CONTEXT}"

# --- Construction de l'image Site B ----------------------------------------- #

echo ""
echo "=== Construction de l'image ${IMAGE_B} ==="
docker build -f "${DOCKERFILE_B}" -t "${IMAGE_B}" "${BUILD_CONTEXT}"

# --- Affichage des tailles et vérification --------------------------------- #

echo ""
echo "=== Tailles des images ==="
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.ID}}" \
    "${IMAGE_A}" "${IMAGE_B}"

echo ""
echo "=== Vérification de la taille (< ${SIZE_LIMIT_MB} Mo) ==="
warnings=0

for image in "${IMAGE_A}" "${IMAGE_B}"; do
    size_mb=$(get_image_size_mb "$image")
    # Comparaison numérique avec bc ou awk
    over_limit=$(echo "${size_mb} > ${SIZE_LIMIT_MB}" | bc -l 2>/dev/null || echo "0")
    if [ "$over_limit" = "1" ]; then
        echo "WARNING: L'image ${image} fait ${size_mb} Mo (limite: ${SIZE_LIMIT_MB} Mo)"
        warnings=$((warnings + 1))
    else
        echo "OK:      L'image ${image} fait ${size_mb} Mo"
    fi
done

echo ""
if [ "$warnings" -gt 0 ]; then
    echo "ATTENTION: ${warnings} image(s) dépassent la limite de ${SIZE_LIMIT_MB} Mo."
    exit 1
else
    echo "Toutes les images respectent la limite de ${SIZE_LIMIT_MB} Mo."
fi

echo ""
echo "=== Build terminé avec succès ==="
