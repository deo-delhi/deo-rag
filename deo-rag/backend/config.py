import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()

# Some enterprise antivirus / SSL-intercept tooling sets SSLKEYLOGFILE to a
# device path (e.g. \\.\aswMonFltProxy\...) that causes PermissionError in
# urllib3/requests when creating SSL contexts. This project does not need TLS
# key logging, so we explicitly disable it to keep ingestion and model downloads
# reliable on locked-down Windows machines.
os.environ.pop("SSLKEYLOGFILE", None)


@dataclass(frozen=True)
class Settings:
    langsmith_api_key: str | None
    database_url: str
    collection_name: str
    llm_provider: str
    embedding_model: str
    embedding_provider: str
    llm_model: str
    ollama_base_url: str
    documents_dir: str
    ingest_chunk_size: int
    ingest_chunk_overlap: int
    ingest_embed_batch_size: int
    ingest_max_workers: int
    # HuggingFace embedding encode batch (0 = use backend defaults: larger on GPU).
    ingest_hf_encode_batch_size: int
    retriever_top_k: int
    llm_temperature: float
    ollama_num_ctx: int
    ollama_num_predict: int
    ollama_request_timeout_seconds: int
    ollama_keep_alive: str
    ask_timeout_seconds: int
    allowed_origins: tuple[str, ...]
    allowed_origin_regex: str | None


def _parse_allowed_origins(raw: str) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


_DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5201",
    "http://127.0.0.1:5201",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


SETTINGS = Settings(
    langsmith_api_key=os.getenv("LANGCHAIN_API_KEY"),
    database_url=os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://admin:admin123@localhost:5202/deorag"
    ),
    collection_name=os.getenv("COLLECTION_NAME", "deo_docs"),
    llm_provider=os.getenv("LLM_PROVIDER", "ollama").lower(),
    embedding_model=os.getenv("EMBEDDING_MODEL", "mxbai-embed-large:latest"),
    embedding_provider=os.getenv("EMBEDDING_PROVIDER", "ollama").lower(),
    llm_model=os.getenv("LLM_MODEL", "llama3.2:latest"),
    ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    documents_dir=os.getenv("DOCUMENTS_DIR", "../documents"),
    ingest_chunk_size=int(os.getenv("INGEST_CHUNK_SIZE", "1000")),
    ingest_chunk_overlap=int(os.getenv("INGEST_CHUNK_OVERLAP", "150")),
    # Number of chunks embedded + inserted into pgvector per batch. Higher values
    # amortize HTTP/DB overhead and let GPU-backed embedders saturate the device.
    ingest_embed_batch_size=int(os.getenv("INGEST_EMBED_BATCH_SIZE", "32")),
    # Number of PDFs whose chunks are embedded concurrently. 0 = autodetect (cpu_count).
    # Set to 1 to disable concurrency. Embedding is I/O- or GPU-bound, so a small
    # pool is usually enough; oversubscribing a single GPU hurts throughput.
    ingest_max_workers=int(os.getenv("INGEST_MAX_WORKERS", "0")),
    ingest_hf_encode_batch_size=int(os.getenv("INGEST_HF_ENCODE_BATCH_SIZE", "0")),
    retriever_top_k=int(os.getenv("RETRIEVER_TOP_K", "4")),
    llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
    ollama_num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "4096")),
    ollama_num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "512")),
    ollama_request_timeout_seconds=int(os.getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "180")),
    # How long Ollama keeps a model resident in VRAM between requests. Long values
    # avoid model reload stalls during ingestion. Use "-1" for "never unload".
    ollama_keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "24h"),
    ask_timeout_seconds=int(os.getenv("ASK_TIMEOUT_SECONDS", "60")),
    allowed_origins=_parse_allowed_origins(os.getenv("ALLOWED_ORIGINS", "")) or _DEFAULT_ALLOWED_ORIGINS,
    allowed_origin_regex=os.getenv("ALLOWED_ORIGIN_REGEX") or None,
)
