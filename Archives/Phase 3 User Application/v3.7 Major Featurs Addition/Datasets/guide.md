# Dataset Guide

This guide explains how to get or access the raw data sources used for ConvoEase dataset preparation.

## Recommended Folder Layout

Store downloaded files under `Datasets/raw/` and keep converted or merged outputs separate, for example:

```text
Datasets/
+-- guide.md
+-- raw/
¦   +-- jigsaw/
¦   +-- hate_speech18/
¦   +-- drive_shared/
+-- processed/
```

## 1. Jigsaw Toxic Comment Classification

Source:
- Kaggle dataset page: <https://www.kaggle.com/datasets/julian3833/jigsaw-toxic-comment-classification-challenge?select=train.csv>

### What it is
This source provides the Jigsaw toxic comment classification challenge files, including `train.csv` on the Kaggle dataset page.

### Access options

#### Option A: Manual download from Kaggle
1. Sign in to your Kaggle account.
2. Open the dataset page.
3. Download the dataset zip from the page.
4. Extract it into `Datasets/raw/jigsaw/`.
5. Confirm that `train.csv` is present.

#### Option B: Kaggle API / CLI
1. Create a Kaggle account if needed.
2. In Kaggle, go to your account settings and create an API token.
3. Download `kaggle.json`.
4. Place it in your user Kaggle config location.
   Windows example: `%USERPROFILE%\\.kaggle\\kaggle.json`
5. Run a download command from the project root:

```bash
kaggle datasets download -d julian3833/jigsaw-toxic-comment-classification-challenge -p Datasets/raw/jigsaw
```

6. Extract the downloaded archive into the same folder.

### Notes for ConvoEase use
- `train.csv` is the main raw file to start from.
- Map toxic or abusive labels into your ConvoEase moderation targets during conversion.
- Keep the original raw file unchanged and do transformations into a separate processed dataset.

## 2. HateSpeech18

Source:
- Hugging Face dataset page: <https://huggingface.co/datasets/odegiber/hate_speech18>

### What it is
The dataset card says this dataset contains English text extracted from Stormfront forum posts, split into sentences and manually labeled. The card lists fields such as:
- `text`
- `user_id`
- `subforum_id`
- `num_contexts`
- `label`

The page also notes that the dataset viewer is disabled because the repo requires arbitrary Python code execution.

### Access options

#### Option A: Load with the Hugging Face `datasets` library
Install the library if needed:

```bash
pip install datasets
```

Then load it in Python:

```python
from datasets import load_dataset

dataset = load_dataset("odegiber/hate_speech18")
print(dataset)
```

#### Option B: Download from the Hugging Face dataset page
1. Open the dataset page.
2. Go to the files section.
3. Download the available source files or clone the dataset repository if you prefer to inspect everything locally.
4. Save the raw files under `Datasets/raw/hate_speech18/`.

### Notes for ConvoEase use
- The `label` field includes more than just binary hate or non-hate categories.
- During conversion, decide how to handle intermediate labels such as relation or skip cases.
- Preserve the original label values in a raw backup or audit column while generating your ConvoEase label.

## 3. Shared Google Drive Dataset

Source:
- Google Drive file: <https://drive.google.com/file/d/1LQnlE6H7hlR2ApKzvJ3Rs4SvdnYeCS9o/view?usp=sharing>

### Access options

#### Option A: Browser download
1. Open the Drive link in a browser.
2. If access is allowed, click `Download`.
3. Save the file into `Datasets/raw/drive_shared/`.
4. Extract it if it is a zip archive.

#### Option B: Direct download by file ID
The Drive file ID in the link is:

```text
1LQnlE6H7hlR2ApKzvJ3Rs4SvdnYeCS9o
```

If you use a Drive downloader tool such as `gdown`, the command pattern is:

```bash
gdown 1LQnlE6H7hlR2ApKzvJ3Rs4SvdnYeCS9o -O Datasets/raw/drive_shared/downloaded_file
```

If the file is permission-restricted, request viewer access from the owner first.

## Shared Drive Dataset Schema

This dataset uses 8 columns:

1. `source`
2. `message`
3. `rules`
4. `context`
5. `label`
6. `reason`
7. `instruction`
8. `response`

### Column meanings

- `source`: origin of the example, such as Kaggle, Hugging Face, manual annotation, or custom synthesis.
- `message`: the main user message to moderate.
- `rules`: the ConvoEase group rules that define the moderation boundary.
- `context`: recent chat history or extra conversational context.
- `label`: expected moderation class.
- `reason`: human-readable explanation for why the item should pass or be flagged.
- `instruction`: the exact ConvoEase system prompt format used for fine-tuning.
- `response`: the target model output.

### Fine-tuning expectation

The `instruction` column is already in the ConvoEase moderation prompt format, so it is ready to feed into your fine-tuning pipeline.

The `response` column should contain one of these formats:

```text
PASS
```

or

```text
FLAGGED: <reason>
```

### Suggested validation checks

Before training, verify that:
- all 8 columns exist
- `message`, `instruction`, and `response` are non-empty
- `response` starts with either `PASS` or `FLAGGED:`
- `label` is consistent with `response`
- there are no accidental spreadsheet header shifts or delimiter errors

## Recommended Workflow

1. Download each raw source into `Datasets/raw/`.
2. Keep raw files unchanged.
3. Convert them into the 8-column ConvoEase schema.
4. Save the converted output under `Datasets/processed/`.
5. Validate the final schema before using it for fine-tuning.

## References

- Kaggle dataset page: <https://www.kaggle.com/datasets/julian3833/jigsaw-toxic-comment-classification-challenge?select=train.csv>
- Hugging Face dataset page: <https://huggingface.co/datasets/odegiber/hate_speech18>
- Hugging Face loading docs: <https://huggingface.co/docs/datasets/loading>
- Google Drive sharing help: <https://support.google.com/docs/answer/2494822>
- Google Drive file: <https://drive.google.com/file/d/1LQnlE6H7hlR2ApKzvJ3Rs4SvdnYeCS9o/view?usp=sharing>
