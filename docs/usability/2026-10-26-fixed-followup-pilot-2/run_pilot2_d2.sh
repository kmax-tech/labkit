#!/bin/zsh
# The twelve pre-registered draws: 4 cases x 3, each on a fresh copy of its case.
# Stops before a draw once the counted cost reaches the cap (10 USD); a failed
# call without a reported cost counts 1 USD. No draw is repeated.
set -u
S=/private/tmp/claude-501/-Users-max-projects-labkit/9e7f87f4-aa12-45f4-85d9-c5adb503e700/scratchpad
OUT=$S/pilot2/draws
LABKIT=/Users/max/projects/labkit/.venv/bin/labkit-audit
mkdir -p $OUT
total=0
for draw in 1 2 3; do
  for c in D2; do
    if (( $(echo "$total >= 3" | bc) )); then
      echo "cap reached before $c-$draw (total $total USD)" | tee -a $OUT/ledger-d2.txt
      exit 0
    fi
    d=$S/pilot2/runs/$c-$draw
    rm -rf $d; mkdir -p $d; cp -R $S/pilot2/$c/work $d/work
    area=$d/work/experiments/01-bulk-modulus
    (cd $d/work && $LABKIT $area --mode analysis --model opus --out $OUT/$c-$draw.report.txt \
       > $OUT/$c-$draw.stdout.txt 2> $OUT/$c-$draw.stderr.txt)
    rc=$?
    cost=$(grep -o '[0-9.]* USD' $OUT/$c-$draw.stderr.txt | tail -1 | cut -d' ' -f1)
    [[ -z "$cost" ]] && cost=1
    total=$(echo "$total + $cost" | bc)
    for f in $area/audits/*-analysis*.toml; do
      [[ $(basename $f) == 2026-10-26T08-* ]] && continue
      cp $f $OUT/$c-$draw.record.toml
    done
    echo "$c-$draw rc=$rc cost=$cost total=$total" | tee -a $OUT/ledger-d2.txt
  done
done
