from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from opensearchpy import OpenSearch
from openai import OpenAI

import os
import uuid
from datetime import datetime

# ===== Config via env =====
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "http://opensearch:9200")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "fake-key")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "mistral")

# ===== Clientes =====
app = FastAPI(title="Log Copilot")

os_client = OpenSearch(
    hosts=[OPENSEARCH_HOST],
    verify_certs=False,
)

oa_client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
)


def ensure_index(index_name: str):
    if not os_client.indices.exists(index=index_name):
        body = {
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "message": {"type": "text"},
                    "source": {"type": "keyword"},
                }
            }
        }
        os_client.indices.create(index=index_name, body=body)


def index_log_lines(index_name: str, content: str, source: str = "upload"):
    ts = datetime.utcnow().isoformat()
    actions = []

    for line in content.splitlines():
        if not line.strip():
            continue
        doc = {
            "@timestamp": ts,
            "message": line,
            "source": source,
        }
        actions.append({"index": {"_index": index_name}})
        actions.append(doc)

    if not actions:
        return 0

    body = "\n".join([os_client.transport.serializer.dumps(a) for a in actions]) + "\n"
    resp = os_client.bulk(body=body)
    return resp.get("items", [])


def call_llm_analyze(log_snippet: str, log_type: str, description: str | None):
    prompt = f"""
Você é um especialista sênior em troubleshooting de infraestrutura (Linux, web servers, proxies, bancos e aplicações).

Recebeu um trecho de LOG e deve:

1. Resumir em no máximo 10 linhas o que está acontecendo.
2. Listar os principais problemas encontrados.
3. Propor de 3 a 5 hipóteses de causa para cada problema.
4. Sugerir de 3 a 5 ações concretas que o administrador pode executar (comandos, verificações, ajustes).

Contexto:
- Tipo de log: {log_type}
- Descrição fornecida pelo usuário (pode estar vazia): {description}

Trechos do log:
```log
{log_snippet}
```
Responda em português, de forma objetiva, usando listas e passos claros.
    """.strip()

    completion = oa_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Você é um especialista em análise de logs e troubleshooting de infraestrutura.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    return completion.choices[0].message.content


@app.get("/")
async def root():
    return {"message": "Log Copilot API OK"}


@app.post("/upload-log")
async def upload_log(
    file: UploadFile = File(...),
    log_type: str = Form("generic"),
    description: str = Form(""),
):
    raw = await file.read()
    content = raw.decode(errors="ignore")

    os.makedirs("/data/logs", exist_ok=True)
    file_id = str(uuid.uuid4())
    save_path = f"/data/logs/{file_id}_{file.filename}"
    with open(save_path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(content)

    index_name = f"logs-{log_type}".lower()
    ensure_index(index_name)
    indexed_items = index_log_lines(index_name, content, source="upload")

    return {
        "file_id": file_id,
        "filename": file.filename,
        "index": index_name,
        "indexed_docs": len(indexed_items),
        "message": "Log salvo e indexado com sucesso.",
    }


@app.post("/analyze-log")
async def analyze_log(
    index: str = Form(...),
    query: str = Form("*"),
    size: int = Form(200),
    description: str = Form(""),
    log_type: str = Form("generic"),
):
    body = {
        "query": {"query_string": {"query": query}},
        "size": size,
        "sort": [{"@timestamp": {"order": "desc"}}],
    }

    resp = os_client.search(index=index, body=body)
    hits = resp.get("hits", {}).get("hits", [])

    if not hits:
        return JSONResponse(
            status_code=404,
            content={"detail": "Nenhum log encontrado para esse filtro."},
        )

    lines = []
    for h in hits:
        src = h.get("_source", {})
        msg = src.get("message", "")
        ts = src.get("@timestamp", "")
        lines.append(f"{ts} {msg}")
    log_snippet = "\n".join(lines)

    analysis = call_llm_analyze(log_snippet, log_type, description)

    return {
        "index": index,
        "query": query,
        "hits_used": len(hits),
        "analysis": analysis,
    }
