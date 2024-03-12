# documents-comparator

Quickly check what differences exist between two PDF documents using an LLM.

## Prerequisites

- a Google Cloud project with billing enabled
- a service account with the role `Vertex AI User` set up + a JSON key for this service account called `vertexai-sa.json` in the root of this repository (it is gitignored)
- a working Python environment

## How to run

- `cp .env.example .env`
- `pip install -r requirements.txt`
- give the app' the two PDF documents to compare, as in `python3 app.py path1 path2`
- check out the results in the `doc_final_summary.md` file, the summaries for each page are listed in the `doc_summary.md` file.
