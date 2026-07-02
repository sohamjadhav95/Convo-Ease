"""Extract and print the full content of Cell 11 (synthesized validation curve) from the notebook."""
import json
from pathlib import Path

NB = Path(r"e:\Projects\Personal\Convo-Ease\Fine_Tune\convoease_finetune.ipynb")
with NB.open(encoding="utf-8") as f:
    nb = json.load(f)

cell = nb["cells"][11]
print(f"Cell type: {cell['cell_type']}")
print("=" * 60)
print("".join(cell.get("source", [])))
