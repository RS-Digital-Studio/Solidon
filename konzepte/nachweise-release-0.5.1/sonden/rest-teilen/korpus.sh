#!/bin/bash
# Sonde RM-266: Korpus der Teilungen, HEAD und Arbeitsbaum je Modell nacheinander.
export PYTHONUTF8=1
P="F:/3D Druck/.venv/Scripts/python.exe"
W="F:/3D Druck.review-051/wt-rest-teilen"
H="F:/3D Druck.review-051/sonden/rest-teilen/head-baum"
S="F:/3D Druck.review-051/sonden/rest-teilen"
D="F:/3D Dateien"
while IFS='|' read -r key file printer; do
  [ -z "$key" ] && continue
  for side in ${SIDES:-head neu}; do
    tree="$H"; [ "$side" = neu ] && tree="$W"
    start=$(date +%s)
    (cd "$tree"; "$P" "$S/teilen_zeit.py" . "$S/laeufe/korpus-$key-$side.json" "$D/$file" "$printer" > "$S/laeufe/korpus-$key-$side.log" 2>&1)
    code=$?
    echo "$key $side exit $code $(( $(date +%s) - start )) s" >> "$S/laeufe/korpus-status.txt"
  done
done < "$S/korpus-liste.txt"
echo fertig >> "$S/laeufe/korpus-status.txt"
