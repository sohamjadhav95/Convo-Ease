"""Search for synthesized/fabricated validation curve code in the finetune notebook."""
import json
from pathlib import Path

NB = Path(r"e:\Projects\Personal\Convo-Ease\Fine_Tune\convoease_finetune.ipynb")

with NB.open(encoding="utf-8") as f:
    nb = json.load(f)

keywords = ["eval_loss", "1.08", "val_loss", "random.gauss", "gauss", "synthetic",
            "fabricat", "simulated", "smoothed", "fake", "approx", "1.0"]

found = []
for idx, cell in enumerate(nb.get("cells", [])):
    src = "".join(cell.get("source", []))
    for kw in keywords:
        if kw.lower() in src.lower():
            found.append((idx, cell.get("cell_type"), kw, src[:500]))
            break

for idx, ct, kw, src in found:
    print(f"Cell {idx} ({ct}) matched [{kw}]:")
    print(f"  {src[:300].replace(chr(10), ' | ')}")
    print()

print(f"Total cells with keywords: {len(found)} out of {len(nb['cells'])} total cells")
