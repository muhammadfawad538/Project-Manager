#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Automated test of the interactive demo with simulated user input.
Shows exactly what the user would see step by step.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from io import StringIO

# ── Setup ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# ── Simulated user input ──────────────────────────────────────────────────────
SIMULATED_INPUT = """\n\n\n\n\n\nDay 1 progress\nDay 2 plan\nNo blockers\n8
Day 2 progress\nDay 3 plan\nWaiting for materials\n6
Day 3 progress\nFinal review\nNo blockers\n8
"""

# ── Run the demo with simulated input ─────────────────────────────────────────
print("=" * 70)
print("  AUTOMATED TEST RUN — Simulated User Input")
print("=" * 70)
print()

# Patch input() to use our simulated input
original_input = __builtins__.__input__ if hasattr(__builtins__, '__input__') else input
input_iter = iter(SIMULATED_INPUT.split('\n'))

def mock_input(prompt=''):
    try:
        line = next(input_iter)
        if line:
            print(f"{prompt}{line}")
        return line
    except StopIteration:
        return ''

__builtins__.__input__ = mock_input
import builtins
builtins.input = mock_input

# Run the demo
try:
    from run_interactive_demo import main
    main()
except SystemExit:
    pass
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
finally:
    # Restore original input
    builtins.input = original_input

print("\n" + "=" * 70)
print("  TEST RUN COMPLETE")
print("=" * 70)
