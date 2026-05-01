# End-to-End DEO Records RAG System using LangChain + LangSmith

## Goal
Build a replacement for RAGFlow that:
- Parses DEO PDFs, scanned reports, prescriptions, discharge summaries, lab reports, and guidelines
- Stores embeddings in a vector database
- Answers questions over uploaded documents
- Tracks every query, retrieval step, hallucination, and latency in LangSmith
- Can later be scaled to multiple users and multiple document collections

---

# 1. Recommended Architecture

Instead of only using LangChain + a vector database, use this stack:

```text
Frontend
    ↓
FastAPI backend
    ↓
LangGraph / LangChain pipeline
    ├── DEO record parser
    ├── Chunking + metadata extraction
    ├── Embedding model
    ├── Vector DB retrieval
    ├── Re-ranking
    ├── LLM answer generation
    └── LangSmith tracing + evaluation
```

Recommended components:

| Layer | Recommended Choice |
|-------|-------|
| Backend | FastAPI |
| Agent orchestration | LangGraph + LangChain |
| Tracing & debugging | LangSmith |
| Document parsing | Docling or Unstructured + OCR |
| OCR for scanned PDFs | PaddleOCR or Tesseract |
| Embedding model | BAAI/bge-large-en-v1.5 or Instructor-XL |
| Vector database | PostgreSQL + pgvector |
| Re-ranking | bge-reranker-large |
| LLM | GPT-4.1, Claude, or local Llama 3.3 / Meditron |
| UI | Streamlit or React |
| Deployment | Docker Compose initially |

For DEO office use cases, PostgreSQL + pgvector is usually better than Chroma because:
- easier backup
- persistent
- production ready
- SQL filtering on case/document metadata
- easy migration later to cloud

---

# 2. Folder Structure

```text
deo-rag/
│
├── backend/
│   ├── app.py
│   ├── ingest.py
│   ├── rag_pipeline.py
│   ├── parser.py
│   ├── config.py
│   └── requirements.txt
│
├── documents/
├── vectorstore/
├── frontend/
├── docker-compose.yml
└── .env
```

---

# 3. Install Requirements

Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows
```

Install packages:

```bash
pip install langchain langgraph langsmith
pip install langchain-openai langchain-community
pip install fastapi uvicorn
pip install psycopg2-binary pgvector sqlalchemy
pip install pypdf pymupdf
pip install unstructured[all-docs]
pip install docling
pip install sentence-transformers
pip install rank-bm25
pip install python-dotenv
pip install tiktoken
pip install paddleocr paddlepaddle
```

If you use OpenAI:

```bash
pip install openai
```

---

# 4. Start PostgreSQL + pgvector

Create `docker-compose.yml`:

```yaml
version: '3.9'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: deo_pgvector
    restart: always
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: admin123
      POSTGRES_DB: deorag
    ports:
      - "5432:5432"
    volumes:
      - ./vectorstore:/var/lib/postgresql/data
```

Run:

```bash
docker compose up -d
```

Then enter PostgreSQL:

```bash
docker exec -it deo_pgvector psql -U admin -d deorag
```

Inside PostgreSQL:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

# 5. Configure LangSmith

Create `.env`:

```text
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=deo-rag
OPENAI_API_KEY=your_openai_key
DATABASE_URL=postgresql://admin:admin123@localhost:5432/deorag
```

Create `config.py`:

```python
from dotenv import load_dotenv
import os

load_dotenv()

LANGSMITH_KEY = os.getenv("LANGCHAIN_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
```

---

# 6. Document Parsing Strategy

DEO records usually contain:
- tables
- scanned handwriting
- headers/footers
- lab values
- page numbers
- multiple columns

Recommended parsing order:

1. Try Docling
2. If scanned PDF → OCR
3. If table-heavy → Unstructured with table extraction
4. Normalize to plain text + metadata

Example parser:

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("documents/report.pdf")
text = result.document.export_to_markdown()
```

Fallback OCR:

```python
from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='en')
```

Save metadata like:

```python
{
  "source": "report.pdf",
  "page": 3,
  "document_type": "lab_report",
  "case_id": "12345"
}
```

---

# 7. Chunking Strategy

For DEO records do NOT use fixed 1000-character chunks only.

Use:
- section-aware chunking
- keep tables together
- preserve page numbers
- overlap of 100–150 tokens

Recommended:

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=120,
    separators=["\n\n", "\n", ". ", " "]
)
```

Store chunk metadata:

```python
metadata={
    "page": 2,
    "section": "Diagnosis",
    "source": "case_report.pdf"
}
```

---

# 8. Embeddings + Vector Store

`ingest.py`

```python
from langchain_community.vectorstores import PGVector
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

vectorstore = PGVector(
    connection_string=DATABASE_URL,
    collection_name="deo_docs",
    embedding_function=embeddings,
)

vectorstore.add_documents(chunks)
```

If you want local embeddings:

```python
from langchain_community.embeddings import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-large-en-v1.5"
)
```

---

# 9. Retrieval + Re-ranking

A better alternative to simple RAGFlow retrieval:

1. BM25 retrieval
2. Dense embedding retrieval
3. Merge results
4. Re-rank with `bge-reranker-large`
5. Send top 5 chunks to LLM

Pseudo pipeline:

```text
User query
   ↓
BM25 top 10
Dense top 10
   ↓
Merge
   ↓
Reranker
   ↓
Top 5 chunks
   ↓
LLM answer
```

This reduces hallucination and improves accuracy on DEO records questions.

---

# 10. Build the RAG Chain

`rag_pipeline.py`

```python
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA

llm = ChatOpenAI(model="gpt-4.1")

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
    return_source_documents=True,
)
```

Prompt template:

```text
You are a DEO record assistant.
Only answer using the provided document context.
If the answer is not present, say:
"The uploaded documents do not contain this information."
Always cite page numbers and document names.
Never invent values.
```

---

# 11. FastAPI Endpoint

`app.py`

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Query(BaseModel):
    question: str

@app.post("/ask")
def ask(query: Query):
    response = qa_chain.invoke({"query": query.question})
    return {
        "answer": response["result"],
        "sources": [
            {
                "page": d.metadata.get("page"),
                "source": d.metadata.get("source")
            }
            for d in response["source_documents"]
        ]
    }
```

Run:

```bash
uvicorn app:app --reload
```

Then query:

```bash
curl -X POST http://127.0.0.1:8000/ask \
-H "Content-Type: application/json" \
-d '{"question":"What medications were prescribed after discharge?"}'
```

---

# 12. Add LangSmith Tracing

Because tracing is enabled in `.env`, every query automatically appears in LangSmith:

You can inspect:
- query
- retrieved chunks
- token usage
- hallucinations
- latency
- failed retrievals

Use LangSmith evaluations later:

```python
from langsmith.evaluation import evaluate
```

You can build automatic tests like:

| Question | Expected answer |
|----------|----------|
| What is the case age? | 54 |
| What medications are listed? | Metformin, Aspirin |
| What is the HbA1c value? | 7.2 |

Then run evaluation after every update.

---

# 13. Dockerize Entire System

Create backend Dockerfile:

```dockerfile
FROM python:3.11

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Updated docker-compose:

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - postgres
```

Run everything:

```bash
docker compose up --build
```

---

# 14. Recommended Production Improvements

After local testing, upgrade in this order:

1. Add multi-document collections
2. Add user login
3. Add Redis cache
4. Add document upload API
5. Add streaming responses
6. Add hybrid retrieval
7. Add citation highlighting
8. Add evaluation dashboard
9. Add human review workflow for DEO records answers
10. Add GraphRAG for relationships between diagnosis, medication, symptoms, and labs

---

# 15. Better Than RAGFlow: Suggested Advanced Pipeline

```text
Upload PDF
   ↓
Docling / OCR
   ↓
Chunk + metadata
   ↓
Store in pgvector
   ↓
Hybrid retrieval (BM25 + embeddings)
   ↓
Reranker
   ↓
LangGraph decision node
      ├── factual question
      ├── table lookup
      ├── medication extraction
      └── summarization
   ↓
LLM response
   ↓
LangSmith trace + evaluation
```

This is significantly more accurate than a standard RAGFlow setup because it:
- preserves tables
- supports OCR
- supports multiple retrieval methods
- provides debugging via LangSmith
- can later become agentic

---

# 16. Minimum Commands to Run End-to-End

```bash
# 1. Start database
docker compose up -d

# 2. Parse and ingest docs
python ingest.py

# 3. Start API
uvicorn app:app --reload

# 4. Ask questions
curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -d '{"question":"What are the abnormal lab values?"}'
```

---

# 17. Best Next Step

Implement in this order:

Day 1:
- PostgreSQL + pgvector
- LangSmith
- Parse 1 PDF

Day 2:
- Chunking + embeddings + retrieval

Day 3:
- FastAPI endpoint

Day 4:
- Re-ranking + evaluation

Day 5:
- Docker + frontend

Once that works, you can completely stop using RAGFlow and move to a more customizable, debuggable, and production-ready system.

