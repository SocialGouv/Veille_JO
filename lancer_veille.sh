#!/usr/bin/env bash
# Veille JO du jour — pendant Linux de `lancer_veille.bat` (poste de développement).
# Usage : double-clic (« Exécuter ») ou `./lancer_veille.sh` dans un terminal.
cd "$(dirname "$0")" || exit 1
.venv/bin/python main.py
code=$?
echo
read -rp "Terminé (code retour $code). Appuyez sur Entrée pour fermer… "
exit $code
