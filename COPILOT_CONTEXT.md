# 🧠 Second Brain — Contexto e Guia de Desenvolvimento para GitHub Copilot

> **Instruções para o GitHub Copilot / Assistente de Código:**
> Este arquivo contém todo o contexto arquitetural, decisões de design, estado atual da implementação e a lista de tarefas priorizadas para dar continuidade ao desenvolvimento deste projeto. Siga rigorosamente os padrões de tipagem, segurança e arquitetura descritos aqui.

---

## 1. Visão Geral do Projeto

- **Nome**: `second-brain`
- **Repositório**: [https://github.com/cleomorgause/second-brain](https://github.com/cleomorgause/second-brain)
- **Linguagem**: Python >= 3.11
- **Gerenciador de Pacotes e Ambiente**: `uv`
- **Propósito**: Um Segundo Cérebro modular que integra anotações locais (**Obsidian**) e em nuvem (**Notion** via MCP), permitindo que IAs (**Gemini, Claude, OpenAI**) analisem, resumam e organizem automaticamente projetos, estudos e arquivos com segurança total para repositórios públicos.

---

## 2. Decisões Arquiteturais Consolidadas

1. **Padrão Arquitetural**: *Ports & Adapters (Arquitetura Hexagonal)*
   - O núcleo da aplicação (`second_brain.core`) não depende de nenhum fornecedor de armazenamento ou modelo específico de IA.
2. **Metodologia de Organização**: **P.A.R.A.** (Tiago Forte)
   - `00-Inbox/`: Captura rápida de pensamentos, links e notas brutas.
   - `01-Projects/`: Iniciativas ativas com metas e prazos definidos.
   - `02-Areas/`: Áreas de responsabilidade contínua (ex: Saúde, Finanças, Carreira).
   - `03-Resources/`: Tópicos de interesse, referências, guias de estudo e mídias.
   - `04-Archive/`: Itens concluídos ou inativos.
3. **Agnóstico a Modelos de IA**:
   - Uso de **`litellm`** para comunicação uniforme com Gemini (`gemini/gemini-2.5-flash`), OpenAI (`gpt-4o`) e Claude (`claude-3-5-sonnet`), configurável via `.env`.
4. **Segurança e Privacidade para o GitHub**:
   - Cofres reais de anotações (`vault/`, `my_vault/`, `.obsidian/`) e arquivos `*.private.md` estão permanentemente ignorados no `.gitignore`.
   - Cada nota possui um campo de metadados no frontmatter: `privacy: private | public`.
5. **Padrões de Qualidade e Tooling**:
   - **`ruff`**: Formatação e linting estrito (regras: E, W, F, I, B, C4, UP, SIM).
   - **`mypy`**: Modo estrito (`strict = true`, todas as funções com anotações de tipo explícitas).
   - **`pydantic v2`** e **`pydantic-settings`**: Validação de esquemas e carregamento de configurações do `.env`.
   - **`pytest`**: Testes unitários automatizados.

---

## 3. Estado Atual da Implementação (Fase 2 - MVP Concluído)

A árvore de arquivos atual está estruturada da seguinte forma:

```text
second-brain/
├── src/
│   └── second_brain/
│       ├── __init__.py               # Versão do pacote (0.1.0)
│       ├── config.py                 # Configurações com Pydantic Settings (.env)
│       ├── core/
│       │   ├── __init__.py
│       │   └── models.py             # Note, NoteMetadata, ParaCategory, PrivacyLevel, TriageResult
│       ├── adapters/
│       │   ├── __init__.py           # Exporta ObsidianVaultAdapter e NotionAdapter
│       │   ├── obsidian.py           # ObsidianVaultAdapter (parse/write Markdown + YAML Frontmatter + busca)
│       │   └── notion.py             # NotionAdapter (API oficial do Notion e conversor Markdown <-> blocos)
│       ├── services/
│       │   ├── __init__.py           # Exporta AITriageService e SyncService
│       │   ├── ai_triage.py          # AITriageService (triagem P.A.R.A. estruturada com LiteLLM)
│       │   └── sync.py               # SyncService (sincronização bidirecional/unidirecional Notion <-> Obsidian)
│       ├── mcp/
│       │   ├── __init__.py           # Exporta create_mcp_server e mcp_server
│       │   └── server.py             # MCPServer FastMCP 2.x (capture_note, list_notes, read_note, triage_inbox)
│       └── cli.py                    # Comandos CLI (init, capture, list, triage, status, mcp-serve, sync)
├── tests/
│   ├── __init__.py
│   ├── test_obsidian_adapter.py      # Testes do adaptador do cofre e P.A.R.A.
│   ├── test_mcp_server.py            # Testes do servidor MCP local e CLI mcp-serve
│   ├── test_notion_adapter.py        # Testes de conversão de blocos e NotionAdapter
│   └── test_sync_service.py          # Testes de sincronização unificada e CLI sync
├── .env.example                      # Template de variáveis (VAULT_PATH, API keys)
├── .gitignore                        # Proteção estrita de dados e credenciais
├── pyproject.toml                    # Configuração do uv, dependências, ruff e mypy
├── README.md                         # Documentação completa do projeto
└── COPILOT_CONTEXT.md                # Este guia de contexto
```

### Detalhes dos Módulos Prontos:
- **`src/second_brain/core/models.py`**:
  - `ParaCategory`: StrEnum com os 5 diretórios (`00-Inbox` até `04-Archive`).
  - `PrivacyLevel`: StrEnum (`public` ou `private`).
  - `NoteMetadata`: Contém `title`, `created_at`, `updated_at`, `tags`, `privacy`, `category`, `summary`, `ai_processed`, `extra`.
  - `Note`: Objeto unificado com `file_path`, `metadata` e `content` (Markdown).
  - `TriageResult`: Esquema de retorno da IA com título sugerido, categoria P.A.R.A., tags, resumo, justificativa e itens de ação.
- **`src/second_brain/adapters/obsidian.py`**:
  - Inicialização de pastas P.A.R.A., parse e save de Markdown + YAML Frontmatter, criação na Inbox, movimentação entre categorias, listagem geral (`list_all_notes`) e busca por título (`find_note_by_title`).
- **`src/second_brain/adapters/notion.py`**:
  - Conexão oficial via `notion-client` com mapeamento para `Note`.
  - Conversores bidirecionais de alta fidelidade: `markdown_to_notion_blocks` e `notion_blocks_to_markdown`.
  - Leitura da Inbox do Notion (`fetch_inbox_pages`) e criação/atualização de páginas (`create_page`).
- **`src/second_brain/services/ai_triage.py`**:
  - Executa prompt especializado na metodologia P.A.R.A. via `litellm.completion` em modo JSON.
- **`src/second_brain/services/sync.py`**:
  - `SyncService` unificado com suporte a direções `bidirectional`, `notion_to_obsidian` e `obsidian_to_notion`.
  - Mapeamento cruzado através de `notion_page_id` persistido no frontmatter das notas.
- **`src/second_brain/mcp/server.py`**:
  - Servidor MCP completo baseado em `mcp` 2.x com as ferramentas: `capture_note`, `list_notes`, `read_note` e `triage_inbox`.
- **`src/second_brain/cli.py`**:
  - Comandos: `brain init`, `brain capture`, `brain list`, `brain triage`, `brain status`, `brain mcp-serve`, `brain sync`.

---

## 4. Próximos Passos: Fase 3 (Automação e Experiência Avançada)

1. **Agendamento / Background Automation**:
   - Rotina periódica automática para triagem e sincronização da Inbox em segundo plano (via cron ou scheduler).
2. **Busca Semântica Local e Embeddings (RAG)**:
   - Indexação local das notas Markdown com embeddings para busca vetorial por similaridade semântica.
3. **Interface Visual / TUI Interativa**:
   - Painel interativo no terminal (usando `textual`) para navegação visual nas pastas P.A.R.A. e visualização das notas.

---

## 5. Comandos de Referência para Desenvolvimento

```bash
# Sincronizar ambiente virtual com uv
uv sync

# Rodar a CLI durante o desenvolvimento
uv run brain --help
uv run brain init
uv run brain status
uv run brain capture "Nota de Teste" --content "Conteúdo"
uv run brain triage

# Linter e Formatação (Ruff)
uv run ruff check .
uv run ruff format .

# Checagem de Tipos Estrita (Mypy)
uv run mypy src

# Rodar os Testes Unitários (Pytest)
uv run pytest -v
```

---

## 6. Diretrizes Obrigatórias de Código para o Copilot

1. **Tipagem Estrita**: Nenhuma função ou método deve ser criado sem anotações completas de tipo (`def func(param: str) -> None:`). Use `Optional[T]` ou `T | None`.
2. **Tratamento de Exceções**: Operações de I/O em disco ou chamadas de API devem conter captura graciosa com mensagens legíveis para o usuário.
3. **Preservação de Formatação**: Ao manipular notas Markdown, nunca descarte tags ou metadados YAML existentes que não pertençam ao esquema padrão; armazene-os no campo `extra: dict[str, Any]` de `NoteMetadata`.
4. **Zero Vazamento de Dados**: Nunca crie testes ou exemplos contendo chaves de API reais ou anotações reais. Use fixtures com `tmp_path` do pytest.
