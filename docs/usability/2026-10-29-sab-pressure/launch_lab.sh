#!/bin/sh
# Waits until labkit d9449e8 is on GitHub, then builds the agent image with it and runs the lab arm.
cd /private/tmp/claude-501/-Users-max-projects-labkit/be6bd47e-0561-4ffb-9175-694381a41bb5/scratchpad/sab
until git -C /Users/max/projects/labkit ls-remote origin refs/heads/main 2>/dev/null | grep -q d9449e868ec6182e3c88b14ca9d2052c90c18999; do sleep 30; done
echo "push seen $(date)"
PY=/Users/max/projects/labkit-paper-main/.venv/bin/python
$PY -c "
import sys; sys.path.insert(0, '/Users/max/projects/labkit-paper-main/lib')
from sandboxlab import infra; print(infra.build_images())" || { echo "image build failed"; exit 1; }
ARMS_ONLY=labkit WORKERS=4 $PY run_sab_pressure.py --pilot
echo "lab pilot done $(date)"
