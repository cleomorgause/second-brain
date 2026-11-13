import contextlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from notion_client import Client
from notion_client.errors import APIResponseError

from second_brain.config import settings
from second_brain.core.models import Note, NoteMetadata, ParaCategory, PrivacyLevel


def extract_plain_text(rich_text_list: list[dict[str, Any]]) -> str:
    """Extrai texto plano de uma lista de objetos rich_text do Notion."""
    return "".join(
        item.get("plain_text", item.get("text", {}).get("content", "")) for item in rich_text_list
    )


def markdown_to_notion_blocks(markdown_text: str) -> list[dict[str, Any]]:
    """Converte texto Markdown simples em uma lista de blocos do Notion.

    Suporta:
    - Cabeçalhos (#, ##, ###)
    - Listas com marcadores (- ou *)
    - Listas numeradas (1.)
    - Tarefas / To-do (- [ ] ou - [x])
    - Citações (>)
    - Blocos de código (```)
    - Divisores (---)
    - Parágrafos
    """
    blocks: list[dict[str, Any]] = []
    lines = markdown_text.splitlines()

    in_code_block = False
    code_lang = "plain text"
    code_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Tratamento de bloco de código com cercadura ```
        if stripped.startswith("```"):
            if in_code_block:
                # Fechamento do bloco de código
                code_content = "\n".join(code_lines)
                blocks.append(
                    {
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": [
                                {"type": "text", "text": {"content": code_content[:2000]}}
                            ],
                            "language": code_lang,
                        },
                    }
                )
                in_code_block = False
                code_lines = []
            else:
                in_code_block = True
                lang = stripped.lstrip("`").strip().lower()
                code_lang = lang if lang else "plain text"
                code_lines = []
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Linha em branco
        if not stripped:
            continue

        # Divisor
        if stripped in ("---", "***", "___"):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            continue

        # Cabeçalhos
        if stripped.startswith("### "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": stripped[4:].strip()}}]
                    },
                }
            )
            continue

        if stripped.startswith("## "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": stripped[3:].strip()}}]
                    },
                }
            )
            continue

        if stripped.startswith("# "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"type": "text", "text": {"content": stripped[2:].strip()}}]
                    },
                }
            )
            continue

        # To-Do (- [ ] ou - [x])
        todo_match = re.match(r"^[-*]\s+\[([ xX])\]\s+(.*)$", stripped)
        if todo_match:
            checked = todo_match.group(1).lower() == "x"
            todo_text = todo_match.group(2)
            blocks.append(
                {
                    "object": "block",
                    "type": "to_do",
                    "to_do": {
                        "rich_text": [{"type": "text", "text": {"content": todo_text}}],
                        "checked": checked,
                    },
                }
            )
            continue

        # Lista com marcadores
        if stripped.startswith(("- ", "* ")):
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": stripped[2:].strip()}}]
                    },
                }
            )
            continue

        # Lista numerada
        num_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if num_match:
            blocks.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": [
                            {"type": "text", "text": {"content": num_match.group(1).strip()}}
                        ]
                    },
                }
            )
            continue

        # Citação
        if stripped.startswith("> "):
            blocks.append(
                {
                    "object": "block",
                    "type": "quote",
                    "quote": {
                        "rich_text": [{"type": "text", "text": {"content": stripped[2:].strip()}}]
                    },
                }
            )
            continue

        # Parágrafo padrão (com limite de 2000 chars por rich_text do Notion)
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": stripped[:2000]}}]
                },
            }
        )

    # Se um bloco de código ficou aberto ao final
    if in_code_block and code_lines:
        blocks.append(
            {
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "\n".join(code_lines)[:2000]}}
                    ],
                    "language": code_lang,
                },
            }
        )

    return blocks


def notion_blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """Converte blocos retornados pela API do Notion em texto Markdown."""
    lines: list[str] = []

    for block in blocks:
        block_type = block.get("type", "")
        data = block.get(block_type, {})

        if block_type == "heading_1":
            text = extract_plain_text(data.get("rich_text", []))
            lines.append(f"# {text}")
        elif block_type == "heading_2":
            text = extract_plain_text(data.get("rich_text", []))
            lines.append(f"## {text}")
        elif block_type == "heading_3":
            text = extract_plain_text(data.get("rich_text", []))
            lines.append(f"### {text}")
        elif block_type == "paragraph":
            text = extract_plain_text(data.get("rich_text", []))
            lines.append(text)
        elif block_type == "bulleted_list_item":
            text = extract_plain_text(data.get("rich_text", []))
            lines.append(f"- {text}")
        elif block_type == "numbered_list_item":
            text = extract_plain_text(data.get("rich_text", []))
            lines.append(f"1. {text}")
        elif block_type == "to_do":
            text = extract_plain_text(data.get("rich_text", []))
            checked = data.get("checked", False)
            mark = "x" if checked else " "
            lines.append(f"- [{mark}] {text}")
        elif block_type == "quote":
            text = extract_plain_text(data.get("rich_text", []))
            lines.append(f"> {text}")
        elif block_type == "code":
            text = extract_plain_text(data.get("rich_text", []))
            lang = data.get("language", "")
            lines.append(f"```{lang}\n{text}\n```")
        elif block_type == "divider":
            lines.append("---")

    return "\n\n".join(line for line in lines if line).strip()


class NotionAdapter:
    """Adaptador para gerenciamento de páginas e notas no Notion via API oficial."""

    def __init__(
        self,
        api_key: str | None = None,
        inbox_database_id: str | None = None,
        client: Client | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.notion_api_key
        self.inbox_database_id = (
            inbox_database_id
            if inbox_database_id is not None
            else settings.notion_inbox_database_id
        )

        self.client: Client | None
        if client is not None:
            self.client = client
        elif self.api_key:
            self.client = Client(auth=self.api_key)
        else:
            self.client = None

    def _ensure_client(self) -> Client:
        """Garante que o cliente da API do Notion está inicializado."""
        if self.client is None:
            raise ValueError(
                "Chave de API do Notion não configurada. Defina NOTION_API_KEY no arquivo .env."
            )
        return self.client

    def page_to_note(self, page: dict[str, Any], content: str = "") -> Note:
        """Converte uma página de base de dados do Notion para o modelo Note unificado."""
        properties = page.get("properties", {})

        # 1. Título: Procura campo do tipo 'title'
        title = "Sem Título"
        for prop_val in properties.values():
            if isinstance(prop_val, dict) and prop_val.get("type") == "title":
                extracted_title = extract_plain_text(prop_val.get("title", []))
                if extracted_title:
                    title = extracted_title
                break

        # 2. Tags: Procura campo multi_select
        tags: list[str] = []
        for prop_name, prop_val in properties.items():
            if (
                isinstance(prop_val, dict)
                and prop_val.get("type") == "multi_select"
                and "tag" in prop_name.lower()
            ):
                tags = [item.get("name", "") for item in prop_val.get("multi_select", [])]
                break
        if not tags:
            # Tenta qualquer multi_select
            for prop_val in properties.values():
                if isinstance(prop_val, dict) and prop_val.get("type") == "multi_select":
                    tags = [item.get("name", "") for item in prop_val.get("multi_select", [])]
                    if tags:
                        break

        # 3. Categoria: Procura campo select
        category = ParaCategory.INBOX
        for _prop_name, prop_val in properties.items():
            if isinstance(prop_val, dict) and prop_val.get("type") == "select":
                select_obj = prop_val.get("select") or {}
                category_name = select_obj.get("name", "")
                if category_name:
                    for cat in ParaCategory:
                        if (
                            category_name.lower() in cat.value.lower()
                            or category_name.lower() in cat.name.lower()
                        ):
                            category = cat
                            break
                    break

        # 4. Resumo: Procura campo rich_text nomeado como resumo/summary
        summary = ""
        for prop_name, prop_val in properties.items():
            if (
                isinstance(prop_val, dict)
                and prop_val.get("type") == "rich_text"
                and ("resumo" in prop_name.lower() or "summary" in prop_name.lower())
            ):
                summary = extract_plain_text(prop_val.get("rich_text", []))
                break

        # 5. Datas de criação e edição
        created_at = datetime.now(UTC)
        if "created_time" in page:
            with contextlib.suppress(ValueError):
                created_at = datetime.fromisoformat(page["created_time"].replace("Z", "+00:00"))

        updated_at = datetime.now(UTC)
        if "last_edited_time" in page:
            with contextlib.suppress(ValueError):
                updated_at = datetime.fromisoformat(page["last_edited_time"].replace("Z", "+00:00"))

        metadata = NoteMetadata(
            title=title,
            created_at=created_at,
            updated_at=updated_at,
            tags=tags,
            privacy=PrivacyLevel.PRIVATE,
            category=category,
            summary=summary,
            ai_processed=bool(summary),
            extra={
                "notion_page_id": page.get("id"),
                "notion_url": page.get("url"),
            },
        )

        return Note(
            file_path=Path(f"notion://{page.get('id', 'unknown')}"),
            metadata=metadata,
            content=content,
        )

    def fetch_page_content(self, page_id: str) -> str:
        """Obtém o conteúdo de texto em Markdown de uma página através de seus blocos filhos."""
        client = self._ensure_client()
        try:
            response = cast(dict[str, Any], client.blocks.children.list(block_id=page_id))
            blocks: list[dict[str, Any]] = response.get("results", [])
            return notion_blocks_to_markdown(blocks)
        except APIResponseError as exc:
            raise RuntimeError(
                f"Erro ao obter blocos da página {page_id} no Notion: {exc}"
            ) from exc

    def fetch_inbox_pages(self, database_id: str | None = None) -> list[Note]:
        """Consulta as páginas cadastradas na Database Inbox do Notion e converte em Note."""
        client = self._ensure_client()
        target_db_id = database_id or self.inbox_database_id

        if not target_db_id:
            raise ValueError(
                "ID da Database do Notion não configurado. Defina NOTION_INBOX_DATABASE_ID."
            )

        try:
            if hasattr(client, "databases") and hasattr(client.databases, "query"):
                query_func = getattr(client.databases, "query")  # noqa: B009
                response = cast(dict[str, Any], query_func(database_id=target_db_id))
            elif hasattr(client, "data_sources") and hasattr(client.data_sources, "query"):
                response = cast(
                    dict[str, Any], client.data_sources.query(data_source_id=target_db_id)
                )
            else:
                response = cast(
                    dict[str, Any], client.search(filter={"value": "page", "property": "object"})
                )
            results: list[dict[str, Any]] = response.get("results", [])
        except APIResponseError as exc:
            raise RuntimeError(
                f"Erro ao consultar a base de dados do Notion ({target_db_id}): {exc}"
            ) from exc

        notes: list[Note] = []
        for page in results:
            page_id = page.get("id", "")
            content = ""
            if page_id:
                try:
                    content = self.fetch_page_content(page_id)
                except Exception:
                    content = ""
            notes.append(self.page_to_note(page, content=content))

        return notes

    def create_page(self, note: Note, database_id: str | None = None) -> dict[str, Any]:
        """Cria ou atualiza uma página no Notion mapeando título, tags, categoria e conteúdo."""
        client = self._ensure_client()
        existing_page_id = note.metadata.extra.get("notion_page_id")

        properties: dict[str, Any] = {
            "title": {"title": [{"type": "text", "text": {"content": note.metadata.title}}]},
        }

        if note.metadata.tags:
            properties["Tags"] = {"multi_select": [{"name": tag} for tag in note.metadata.tags]}

        if note.metadata.category:
            properties["Category"] = {"select": {"name": note.metadata.category.value}}

        if note.metadata.summary:
            properties["Summary"] = {
                "rich_text": [{"type": "text", "text": {"content": note.metadata.summary[:2000]}}]
            }

        try:
            if existing_page_id:
                # Atualização de página existente
                update_result = cast(
                    dict[str, Any],
                    client.pages.update(page_id=existing_page_id, properties=properties),
                )
                return update_result

            target_db_id = database_id or self.inbox_database_id
            if not target_db_id:
                raise ValueError(
                    "ID da base de dados do Notion não informado para criação de página."
                )

            blocks = markdown_to_notion_blocks(note.content) if note.content else []
            create_payload: dict[str, Any] = {
                "parent": {"database_id": target_db_id},
                "properties": properties,
            }
            if blocks:
                create_payload["children"] = blocks[:100]  # Limite máximo de blocos por chamada

            create_result = cast(dict[str, Any], client.pages.create(**create_payload))
            page_id = create_result.get("id")
            if page_id:
                note.metadata.extra["notion_page_id"] = page_id
                note.metadata.extra["notion_url"] = create_result.get("url")

            return create_result
        except APIResponseError as exc:
            raise RuntimeError(f"Erro ao salvar página no Notion: {exc}") from exc
