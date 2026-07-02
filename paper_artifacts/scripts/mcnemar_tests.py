"""
Task 2: Dedicated McNemar test script (alias/thin wrapper around compute_metrics.py).
Runs the three paired comparisons and prints the full tables.
All computation is done in compute_metrics.py; this file just re-runs that script
and presents results. To avoid duplication, import directly.
"""
import sys
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# compute_metrics.py contains both metrics AND mcnemar tests
import compute_metrics
compute_metrics.main()
