#!/bin/sh
# Lance le serveur Ollama en arrière-plan
/bin/ollama serve &

# Stocke le PID du serveur
pid=$!

# Attend que le serveur soit réellement joignable en local
echo "Attente du démarrage d'Ollama..."
until ollama list > /dev/null 2>&1; do
  sleep 1
done

# Vérifie si le modèle qwen2.5:7b est déjà présent, sinon le télécharge
if ! ollama list | grep -q "qwen2.5"; then
  echo "Modèle qwen2.5:7b introuvable. Téléchargement en cours..."
  ollama pull qwen2.5:7b
else
  echo "Modèle qwen2.5:7b déjà présent."
fi

# Garde le processus principal actif (attend la fin du serveur Ollama)
wait $pid
