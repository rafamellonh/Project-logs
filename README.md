# 🧠 Log Copilot – Analisador Inteligente de Logs com ChatGPT + OpenSearch + n8n

## 🚀 Visão Geral

O **Log Copilot** é uma solução completa e open source para **análise inteligente de logs**.  
Ele combina **OpenSearch**, **FastAPI**, **ChatGPT (OpenAI)** e **n8n** para criar um fluxo onde:

- O usuário faz **upload de arquivos de log** (Apache, Varnish, app, etc.)
- Os logs são **armazenados e indexados** no **OpenSearch**
- A API `Log Copilot` consulta os logs e envia trechos relevantes para o **ChatGPT**
- O **n8n** orquestra todo o processo, grava um histórico no **Google Sheets** e devolve uma análise completa ao usuário

---

## 🧩 Arquitetura

**Componentes principais:**

| Camada | Tecnologia | Função |
|--------|-------------|--------|
| Armazenamento de logs | **OpenSearch 2.x** | Banco de logs full text |
| Visualização | **OpenSearch Dashboards** | UI para explorar logs |
| API | **FastAPI (Python)** | Ingestão, análise e integração com ChatGPT |
| Automação | **n8n** | Recebe uploads, orquestra a análise e atualiza KB |
| Base de conhecimento | **Google Sheets** | Armazena casos analisados |
| Banco relacional (opcional) | **PostgreSQL 16** | Metadados e histórico interno |

---

## 🧱 Stack Tecnológica

- **Docker + Docker Compose**
- **Python 3.12 + FastAPI + Uvicorn**
- **OpenAI API (ChatGPT 4o-mini)**
- **OpenSearch + Dashboards**
- **PostgreSQL 16**
- **n8n (Automation)**
- **Google Sheets (Base de Conhecimento)**

---

## ⚙️ Pré-requisitos

- Docker e Docker Compose instalados
- Conta OpenAI com uma **API key** (`OPENAI_API_KEY`)
- Conta Google para integração com **Google Sheets**
- Portas disponíveis:  
  `9200` (OpenSearch) • `5601` (Dashboards) • `8080` (API) • `5678` (n8n)

---

## 🗂️ Estrutura do Projeto

```text
log-copilot/
├─ docker-compose.yml
├─ data/
│  └─ logs/                # onde os uploads vão ficar
└─ app/
   ├─ Dockerfile
   ├─ requirements.txt
   └─ main.py
```

---

## 🐋 Docker Compose (Stack Completa)

```yaml
version: "3.8"

services:
  opensearch:
    image: opensearchproject/opensearch:2
    container_name: opensearch
    environment:
      - cluster.name=logcopilot-os-cluster
      - node.name=opensearch-node1
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g"
      - plugins.security.disabled=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    volumes:
      - opensearch-data:/usr/share/opensearch/data
    ports:
      - "9200:9200"
    networks:
      - logcopilot-net
    restart: unless-stopped

  dashboards:
    image: opensearchproject/opensearch-dashboards:2
    container_name: opensearch-dashboards
    environment:
      - OPENSEARCH_HOSTS=["http://opensearch:9200"]
      - OPENSEARCH_SECURITY_ENABLED=false
      - SERVER_HOST=0.0.0.0
    depends_on:
      - opensearch
    ports:
      - "5601:5601"
    networks:
      - logcopilot-net
    restart: unless-stopped

  db:
    image: postgres:16
    container_name: logcopilot-db
    environment:
      - POSTGRES_USER=logcopilot
      - POSTGRES_PASSWORD=logcopilot
      - POSTGRES_DB=logcopilot
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - logcopilot-net
    restart: unless-stopped

  app:
    build: ./app
    container_name: logcopilot-app
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DB_HOST=db
      - DB_PORT=5432
      - DB_USER=logcopilot
      - DB_PASSWORD=logcopilot
      - DB_NAME=logcopilot
      - OPENSEARCH_HOST=http://opensearch:9200
    volumes:
      - ./data/logs:/data/logs
    depends_on:
      - db
      - opensearch
    ports:
      - "8080:8080"
    networks:
      - logcopilot-net
    restart: unless-stopped

  n8n:
    image: n8nio/n8n
    container_name: n8n
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=admin123
      - N8N_HOST=localhost
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - NODE_ENV=production
    volumes:
      - ./n8n_data:/home/node/.n8n
    depends_on:
      - app
      - opensearch
    networks:
      - logcopilot-net
    restart: unless-stopped

volumes:
  opensearch-data:
  pgdata:

networks:
  logcopilot-net:
    driver: bridge
```

---

## 🧠 Aplicação FastAPI (`app/`)

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Requirements

```text
fastapi
uvicorn[standard]
openai
opensearch-py
psycopg2-binary
SQLAlchemy
python-multipart
```

### API (`main.py`)

> Endpoints:  
> - `/upload-log` – recebe e indexa o log  
> - `/analyze-log` – consulta o OpenSearch e envia para ChatGPT

[O conteúdo completo do `main.py` está incluído no repositório.]

---

## 🔁 Fluxo no n8n (upload manual)

### Descrição

Workflow: **“Manual Log Upload → LogCopilot → KB → Response”**

1. **Webhook – Recebe o upload**
2. **HTTP – Envia para /upload-log**
3. **HTTP – Chama /analyze-log**
4. **Google Sheets – Armazena caso na KB**
5. **Respond to Webhook – Retorna análise ao usuário**

### Exemplo de `curl`

```bash
curl -X POST "http://localhost:5678/webhook/log-upload"   -F "file=@/var/log/httpd/error_log"   -F "log_type=apache"   -F "description=Erros 500 na aplicação"
```

### Exemplo de resposta

```json
{
  "index": "logs-apache",
  "query": "ERROR OR 500 OR 502",
  "hits_used": 150,
  "analysis": "Resumo do problema e sugestões do ChatGPT..."
}
```

---

## 📊 Base de Conhecimento (Google Sheets)

Crie uma planilha chamada **KB_Logs** com as colunas:

| timestamp | arquivo | log_type | index | query | descricao_usuario | analysis | tags |
|------------|----------|-----------|--------|--------|--------------------|-----------|-------|

Cada upload feito via n8n criará automaticamente uma nova linha.

---

## 🧭 Passo a Passo de Implementação

```bash
# 1. Clonar e acessar o projeto
git clone https://github.com/seuusuario/log-copilot.git
cd log-copilot

# 2. Configurar API Key da OpenAI
export OPENAI_API_KEY="sua_api_key_aqui"

# 3. Subir os containers
docker compose up -d

# 4. Acessar os serviços
# API: http://localhost:8080/docs
# Dashboards: http://localhost:5601
# n8n: http://localhost:5678
```

Depois de subir o ambiente:

1. Crie a planilha KB_Logs no Google Sheets.
2. Configure o workflow no n8n.
3. Teste o upload de um log via cURL ou formulário.
4. Veja o resultado:
   - Análise no retorno HTTP
   - Log indexado no OpenSearch
   - Caso registrado no Google Sheets

---

## 🧩 Extensões Futuras

- 🔐 Autenticação e controle de acesso à API e n8n  
- 📈 Envio automático de logs (Filebeat / Fluent Bit)  
- 🧾 Integração com Notion / GitHub Issues como base de conhecimento alternativa  
- 🧰 Dashboard web para upload direto via navegador  
- ⚙️ Automação de playbooks via n8n (reinícios, healthchecks, etc.)  

---

## 💡 Créditos

Criado com ❤️ por Rafael Mello.  
Infraestrutura e automação pensadas para administradores de sistemas e engenheiros DevOps que desejam **analisar, aprender e agir** com base em logs.

---

> 🧠 “Não é só observar os logs — é entender o que eles tentam dizer.”
