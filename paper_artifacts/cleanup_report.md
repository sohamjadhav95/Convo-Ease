# Repository Cleanup Report

## Preconditions
- **NVIDIA API Key Rotation**: **CONFIRMED**. The key has been rotated on the NVIDIA dashboard.

## Tasks Summary

### Task A: Backup First
- **Status**: **DONE**
- **Details**: Created a mirror clone at `../Convo-Ease-backup-20260702.git`.

### Task B: Remove Hardcoded API Key
- **Status**: **DONE**
- **Details**: Replaced the hardcoded API key in `config.py` and various test scripts (`testing/api testing/nvidia_text.py`, `testing/api testing/nvidia_image.py`) with environment variable lookups. Created `.env.example` and confirmed `.env` is ignored in `.gitignore`. Also purged key from `Archives/` copies. All occurrences of `nvapi-...` placeholders in `README.md` and `api_key_env_patch.diff` were swapped out for safe strings.

### Task C: Add a LICENSE
- **Status**: **DONE**
- **Details**: Created `LICENSE` file using the **MIT License** with copyright year 2026 and author "Soham S. Jadhav".
- **IMPORTANT**: The raw message texts used in the evaluation datasets were derived from the Jigsaw Toxic Comment Classification and HateSpeech18 datasets. To respect their redistribution terms, the raw text columns have been excluded from the published dataset (see Task F).

### Task D: Fix requirements.txt
- **Status**: **DONE**
- **Details**: Appended `statsmodels` and `scipy` to `requirements.txt`.
- **Dependency State**:
  - Unpinned dependencies include: `statsmodels`, `scipy`, `pyttsx3`, `torch`, `transformers`, `protobuf`, `pillow`, `numpy`.
  - **Fine-tuning dependencies**: `torch` and `transformers>=5.3.0` are present but **commented out**. `trl` is **absent**. This implies fine-tuning may not be reproducible purely from the current `requirements.txt`.

### Task E: Fine-Tuning Notebook Eval-Loss Curve
- **Status**: **DONE** (Excluded)
- **Details**: As requested, the fine-tuning workflow has been entirely excluded from the release scope. The `Fine_Tune/` directory has been removed from git tracking and added to `.gitignore`.

### Task F: Stage paper_artifacts
- **Status**: **DONE** (Safe Default)
- **Details**: Implemented the **Safe Default** approach. Extracted non-PII prediction data into `paper_artifacts/benchmark_predictions_public.csv` (excluding the raw message, rules, and context text columns) to preserve reproducibility without data redistribution risks. The original `paper_artifacts/benchmark_raw_1200.csv` has been untracked from git and ignored.

### Task G: README Reproduction Section
- **Status**: **DONE**
- **Details**: Added instructions at the bottom of `README.md` detailing how to install requirements, set up API keys, and run the metric verification scripts.

### Task H: Scrub Key from Git History
- **Status**: **NOT DONE** (Intentionally Skipped)
- **Details**: User declined scrubbing the git history since the repository state is only relevant as a Zenodo source snapshot and the key was already revoked.

---

## 🔨 Remaining Manual Steps for You
- **Review and Commit Changes**: Run `git commit -a -m "Prepare for Zenodo release"` and `git push`.
- **Create the GitHub release**.
- **Connect to Zenodo** and generate the DOI using the new release tag.
