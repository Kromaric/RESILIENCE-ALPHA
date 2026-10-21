#!/bin/sh
# Télécharge les modèles Ollama dans le volume partagé, puis s'arrête (conteneur ollama-init).
#
# Exécuté avec un serveur Ollama temporaire, sur un réseau qui a accès à Internet. Le conteneur
# « ollama » qui sert l'assistant, lui, reste sur un réseau interne sans accès à Internet.
# Un modèle déjà présent n'est pas retéléchargé : la pile redémarre donc aussi hors ligne
# (hotspot du campus) une fois le premier téléchargement fait.
set -eu

: "${LLM_MODEL:?LLM_MODEL manquant}"
: "${EMBED_MODEL:?EMBED_MODEL manquant}"

ollama serve >/tmp/ollama-serve.log 2>&1 &
SERVER=$!
trap 'kill "$SERVER" 2>/dev/null || true' EXIT

i=0
until ollama list >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 30 ]; then
    echo "Le serveur Ollama temporaire ne démarre pas :" >&2
    cat /tmp/ollama-serve.log >&2
    exit 1
  fi
  sleep 1
done

for model in $LLM_MODEL $EMBED_MODEL; do
  case "$model" in *:*) tagged="$model" ;; *) tagged="$model:latest" ;; esac
  if ollama list | awk 'NR > 1 { print $1 }' | grep -qx "$tagged"; then
    echo "présent      $tagged"
  else
    echo "téléchargement $tagged"
    ollama pull "$tagged"
  fi
done

ollama list
