# 🧠 Second Brain (Segundo Cérebro com IA, Obsidian & Notion)

> Um assistente inteligente e modular de Segundo Cérebro projetado para organizar seu conhecimento localmente no **Obsidian** e na nuvem no **Notion**, integrando **IA (Google Gemini, OpenAI ChatGPT, Anthropic Claude)** e **MCP (Model Context Protocol)** com privacidade garantida para repositórios públicos.

---

## 🚀 Destaques do Projeto

- **Local-First & Nuvem (Híbrido)**: Funcione puramente offline no **Obsidian**, puramente na nuvem no **Notion**, ou mantenha ambos sincronizados bidirecionalmente.
- **Seguro para Repositórios Públicos**: O cofre de anotações pessoais (`my_vault/`) e as credenciais (`.env`) estão protegidos no `.gitignore`.
- **Metodologia P.A.R.A. (Tiago Forte)**: Organização estruturada em:
  - `00-Inbox/`: Captura rápida de ideias, links e notas brutas.
  - `01-Projects/`: Iniciativas com metas e prazos definidos.
  - `02-Areas/`: Áreas de responsabilidade contínua (ex: Saúde, Finanças, Carreira).
  - `03-Resources/`: Tópicos de interesse, estudos, referências e guias.
  - `04-Archive/`: Itens concluídos, inativos ou descartes.
- **Triagem Inteligente com IA**: Analisa as notas da Inbox e sugere título, resumo, tags contextuais e categoria P.A.R.A. automaticamente.
- **Servidor MCP Embutido**: Permite que assistentes como **Claude Desktop**, **Antigravity** e **Cursor** manipulem suas notas via linguagem natural.
- **Qualidade de Código Profissional**: 100% tipado com **Mypy (Strict)**, formatado e auditado com **Ruff**, modelos com **Pydantic v2** e testes automatizados com **Pytest**.

---

## 📁 Estrutura do Repositório

```text
second-brain/
├── src/
│   └── second_brain/
│       ├── adapters/          # Adaptadores de armazenamento
│       │   ├── obsidian.py    # Leitura/escrita de Markdown com YAML Frontmatter
│       │   └── notion.py      # Integração oficial Notion API e conversão de blocos
│       ├── core/              # Modelos universais (Note, ParaCategory, NoteMetadata)
│       │   └── models.py
│       ├── services/          # Regras de negócio
│       │   ├── ai_triage.py   # Triagem com IA via LiteLLM
│       │   └── sync.py        # Sincronização unificada Notion <-> Obsidian
│       ├── mcp/               # Servidor Model Context Protocol
│       │   └── server.py      # Tools: capture_note, list_notes, read_note, triage_inbox
│       ├── cli.py             # Interface de linha de comando (Typer + Rich)
│       └── config.py          # Configurações com Pydantic Settings
├── tests/                     # Suíte de testes unitários automatizados
├── .env.example               # Template de variáveis de ambiente
├── .gitignore                 # Proteção contra vazamento de notas e segredos
├── pyproject.toml             # Configuração do uv, dependências e linters
└── README.md
```

---

## 🛠️ Instalação Rápida

Este projeto utiliza o [uv](https://github.com/astral-sh/uv) para gerenciamento ultra-rápido de dependências e ambiente Python (>= 3.11).

```bash
# 1. Clone o repositório
git clone https://github.com/cleomorgause/second-brain.git
cd second-brain

# 2. Crie o ambiente virtual e sincronize as dependências
uv sync
```

*(Caso não tenha o `uv` instalado, execute `pip install uv`).*

### Configuração do `.env`

Copie o arquivo de exemplo para criar seu `.env`:

```bash
cp .env.example .env
```

Abra o arquivo `.env` e configure conforme o seu uso:

```env
# Caminho para o cofre do Obsidian local (relativo ou absoluto)
VAULT_PATH=./my_vault

# Chave do modelo de IA (Obtenha gratuitamente no Google AI Studio: aistudio.google.com)
GEMINI_API_KEY=sua_chave_do_gemini_aqui
DEFAULT_AI_MODEL=gemini/gemini-2.5-flash

# Opcional: Se quiser usar OpenAI ou Anthropic
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=

# Opcional: Se for usar a sincronização com o Notion
NOTION_API_KEY=ntn_sua_chave_de_integracao_aqui
NOTION_INBOX_DATABASE_ID=id_da_sua_database_no_notion
```

---

## 📖 Como Usar

Você pode rodar os comandos ativando o ambiente virtual (`.\.venv\Scripts\activate` no Windows ou `source .venv/bin/activate` no Linux/Mac) ou usando `uv run brain`:

### 1. Diagnóstico do Ambiente
Verifique se seus caminhos e chaves de API estão devidamente detectados:
```bash
uv run brain status
```

---

### 2. Usando com o Obsidian (Modo Local)

1. **Inicializar a estrutura P.A.R.A.:**
   ```bash
   uv run brain init
   ```
   Isso criará as pastas `00-Inbox`, `01-Projects`, `02-Areas`, `03-Resources` e `04-Archive` dentro do diretório configurado em `VAULT_PATH`.

2. **Abrir no Obsidian:**
   - Abra o **Obsidian**.
   - Clique em **"Open folder as vault"** (*Abrir pasta como cofre*).
   - Selecione a pasta `my_vault/` do projeto.

3. **Capturar notas rápidas via terminal:**
   ```bash
   uv run brain capture "Pesquisa sobre MCP" --content "Estudar o protocolo FastMCP da Anthropic." --tags "ia,estudo"
   ```

4. **Triagem Automática com IA:**
   ```bash
   uv run brain triage
   ```
   A IA analisará cada nota da sua Inbox, apresentará sugestão de título, categoria P.A.R.A., resumo e tags, e pedirá sua confirmação para mover o arquivo automaticamente.

5. **Visualizar suas notas organizadas:**
   ```bash
   uv run brain list
   ```

---

### 3. Usando com o Notion (Modo Nuvem / Mobile)

Você pode capturar notas pelo celular ou web no Notion e sincronizá-las diretamente com o seu Segundo Cérebro:

1. **Criar a Integração no Notion:**
   - Acesse [notion.so/profile/integrations](https://www.notion.so/profile/integrations) e crie uma nova integração (ex: *Second Brain*).
   - Copie a **Internal Integration Secret** e cole em `NOTION_API_KEY` no seu `.env`.

2. **Criar a Database no Notion:**
   - Crie uma página do tipo **Table (Tabela)** no Notion chamada `Inbox`.
   - Adicione as colunas: `Tags` (Multi-select), `Category` (Select) e `Summary` (Rich text).
   - **Importante**: Clique nos `...` no canto superior direito da página ➔ **Connect to** (Conectar a) ➔ Selecione **Second Brain**.
   - Copie o link da tabela e extraia os 32 caracteres do ID para a variável `NOTION_INBOX_DATABASE_ID` no `.env`.

3. **Sincronizar:**
   ```bash
   # Sincronização nos dois sentidos (Notion <-> Obsidian)
   uv run brain sync --direction bidirectional

   # Ou apenas baixar as notas do Notion para o Obsidian local
   uv run brain sync --direction notion-to-obsidian

   # Ou enviar notas do Obsidian local para o Notion
   uv run brain sync --direction obsidian-to-notion
   ```

---

### 4. Usando como Servidor MCP (Claude Desktop, Antigravity, Cursor)

O Second Brain inclui um servidor **MCP (Model Context Protocol)** que expõe ferramentas para que qualquer IA possa interagir com o seu cofre:

```bash
# Rodar via stdio (para Claude Desktop ou Cursor)
uv run brain mcp-serve --transport stdio

# Ou rodar via SSE (HTTP local)
uv run brain mcp-serve --transport sse --port 8000
```

#### Ferramentas MCP expostas:
- `capture_note`: Captura de notas diretamente para a Inbox.
- `list_notes`: Listagem de notas com filtro por categoria P.A.R.A.
- `read_note`: Leitura completa de conteúdo Markdown e metadados.
- `triage_inbox`: Dispara a triagem automática de notas pendentes da Inbox.

---

## 🧪 Qualidade de Código e Testes

O projeto segue rigorosos padrões de qualidade e conta com uma suíte de testes completa:

```bash
# Executar a suíte de testes unitários (Pytest)
uv run pytest -v

# Validação estrita de tipos estáticos (Mypy)
uv run mypy src tests

# Verificação de linting e formatação (Ruff)
uv run ruff check .
uv run ruff format --check .
```

---

## 🗺️ Roadmap de Evolução

- [x] **Fase 1: Prova de Conceito (POC)**
  - Suporte a Markdown local e Obsidian com metadados YAML.
  - Metodologia P.A.R.A. implementada.
  - Triagem assistida por IA (LiteLLM com suporte a Gemini, OpenAI, Claude).
  - CLI interativa com Rich e Typer.
- [x] **Fase 2: Mínimo Produto Viável (MVP)**
  - Servidor MCP local (`mcp-serve`) para Claude Desktop, Antigravity e Cursor.
  - Adaptador completo para a API do Notion com conversores bidirecionais de blocos Markdown.
  - Serviço de sincronização unificada (`brain sync`) bidirecional e unidirecional.
- [ ] **Fase 3: Automação e Experiência Avançada**
  - Automação periódica em segundo plano (scheduler / cron jobs para sync e triage automáticos).
  - Indexação semântica local com Embeddings (RAG) para busca vetorial no cofre.
  - Interface TUI interativa no terminal (via Textual).

---

## 📄 Licença

Distribuído sob a licença MIT. Consulte `LICENSE` para mais informações.
