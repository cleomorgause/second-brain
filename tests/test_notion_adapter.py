"""Testes unitários para o adaptador do Notion e conversores de blocos Markdown."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from notion_client.errors import APIResponseError

from second_brain.adapters.notion import (
    NotionAdapter,
    markdown_to_notion_blocks,
    notion_blocks_to_markdown,
)
from second_brain.core.models import Note, NoteMetadata, ParaCategory, PrivacyLevel


def test_markdown_to_notion_blocks_conversion() -> None:
    """Testa a conversão de diferentes elementos Markdown para blocos Notion."""
    md = """# Título Principal
## Subtítulo
### Detalhe

Parágrafo normal de texto.

- Item de lista 1
- Item de lista 2

1. Primeiro passo
2. Segundo passo

- [ ] Tarefa pendente
- [x] Tarefa concluída

> Frase de impacto

```python
x = 42
print(x)
```

---
"""
    blocks = markdown_to_notion_blocks(md)

    assert len(blocks) == 13
    assert blocks[0]["type"] == "heading_1"
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Título Principal"

    assert blocks[1]["type"] == "heading_2"
    assert blocks[2]["type"] == "heading_3"

    assert blocks[3]["type"] == "paragraph"
    assert blocks[3]["paragraph"]["rich_text"][0]["text"]["content"] == "Parágrafo normal de texto."

    assert blocks[4]["type"] == "bulleted_list_item"
    assert blocks[5]["type"] == "bulleted_list_item"

    assert blocks[6]["type"] == "numbered_list_item"
    assert blocks[7]["type"] == "numbered_list_item"

    assert blocks[8]["type"] == "to_do"
    assert blocks[8]["to_do"]["checked"] is False
    assert blocks[9]["type"] == "to_do"
    assert blocks[9]["to_do"]["checked"] is True

    assert blocks[10]["type"] == "quote"

    assert blocks[11]["type"] == "code"
    assert blocks[11]["code"]["language"] == "python"
    assert "x = 42" in blocks[11]["code"]["rich_text"][0]["text"]["content"]

    assert blocks[12]["type"] == "divider"


def test_notion_blocks_to_markdown_conversion() -> None:
    """Testa a conversão inversa de blocos Notion para Markdown formatado."""
    blocks = [
        {
            "type": "heading_1",
            "heading_1": {"rich_text": [{"plain_text": "Cabeçalho 1"}]},
        },
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": "Um parágrafo explicativo."}]},
        },
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"plain_text": "Ponto importante"}]},
        },
        {
            "type": "to_do",
            "to_do": {"rich_text": [{"plain_text": "Comprar café"}], "checked": True},
        },
        {
            "type": "to_do",
            "to_do": {"rich_text": [{"plain_text": "Lavar caneca"}], "checked": False},
        },
        {
            "type": "code",
            "code": {
                "rich_text": [{"plain_text": "console.log('hello');"}],
                "language": "javascript",
            },
        },
        {
            "type": "divider",
            "divider": {},
        },
    ]

    md = notion_blocks_to_markdown(blocks)

    assert "# Cabeçalho 1" in md
    assert "Um parágrafo explicativo." in md
    assert "- Ponto importante" in md
    assert "- [x] Comprar café" in md
    assert "- [ ] Lavar caneca" in md
    assert "```javascript\nconsole.log('hello');\n```" in md
    assert "---" in md


def test_page_to_note_mapping() -> None:
    """Testa o mapeamento correto de uma página do Notion para a estrutura Note."""
    mock_page = {
        "id": "page-uuid-1234",
        "url": "https://notion.so/page-uuid-1234",
        "created_time": "2026-10-18T10:00:00.000Z",
        "last_edited_time": "2026-10-18T12:00:00.000Z",
        "properties": {
            "Nome": {
                "type": "title",
                "title": [{"plain_text": "Plano de Estudos em IA"}],
            },
            "Tags": {
                "type": "multi_select",
                "multi_select": [{"name": "estudos"}, {"name": "ia"}],
            },
            "Category": {
                "type": "select",
                "select": {"name": "03-Resources"},
            },
            "Summary": {
                "type": "rich_text",
                "rich_text": [{"plain_text": "Resumo dos estudos de LLM e arquitetura."}],
            },
        },
    }

    adapter = NotionAdapter(api_key="secret_test")
    note = adapter.page_to_note(mock_page, content="Conteúdo Markdown de teste.")

    assert note.metadata.title == "Plano de Estudos em IA"
    assert note.metadata.category == ParaCategory.RESOURCES
    assert note.metadata.tags == ["estudos", "ia"]
    assert note.metadata.summary == "Resumo dos estudos de LLM e arquitetura."
    assert note.metadata.ai_processed is True
    assert note.metadata.extra["notion_page_id"] == "page-uuid-1234"
    assert note.metadata.extra["notion_url"] == "https://notion.so/page-uuid-1234"
    assert note.content == "Conteúdo Markdown de teste."


def test_fetch_inbox_pages_with_mock_client() -> None:
    """Testa a leitura de páginas da Inbox do Notion com um cliente mockado."""
    mock_client = MagicMock()
    mock_client.databases.query.return_value = {
        "results": [
            {
                "id": "page-1",
                "properties": {
                    "Title": {"type": "title", "title": [{"plain_text": "Nota 1 Notion"}]},
                    "Tags": {"type": "multi_select", "multi_select": [{"name": "inbox"}]},
                },
            }
        ]
    }
    mock_client.blocks.children.list.return_value = {
        "results": [
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Texto vindo do Notion."}]},
            }
        ]
    }

    adapter = NotionAdapter(client=mock_client, inbox_database_id="db-inbox-123")
    notes = adapter.fetch_inbox_pages()

    assert len(notes) == 1
    assert notes[0].metadata.title == "Nota 1 Notion"
    assert notes[0].metadata.tags == ["inbox"]
    assert notes[0].content == "Texto vindo do Notion."
    mock_client.databases.query.assert_called_once_with(database_id="db-inbox-123")
    mock_client.blocks.children.list.assert_called_once_with(block_id="page-1")


def test_fetch_inbox_pages_missing_database_id_raises_value_error() -> None:
    """Verifica se fetch_inbox_pages levanta ValueError quando não há database_id configurado."""
    mock_client = MagicMock()
    adapter = NotionAdapter(client=mock_client, inbox_database_id=None)

    with pytest.raises(ValueError, match="ID da Database do Notion não configurado"):
        adapter.fetch_inbox_pages()


def test_fetch_inbox_pages_api_error_handling() -> None:
    """Verifica o tratamento gracioso de erros da API do Notion ao buscar páginas."""
    import httpx

    mock_client = MagicMock()
    mock_client.databases.query.side_effect = APIResponseError(
        code="object_not_found",
        status=404,
        message="Database not found",
        headers=httpx.Headers(),
        raw_body_text="{}",
    )

    adapter = NotionAdapter(client=mock_client, inbox_database_id="db-invalid")

    with pytest.raises(RuntimeError, match="Erro ao consultar a base de dados do Notion"):
        adapter.fetch_inbox_pages()


def test_create_page_new_note() -> None:
    """Testa a criação de uma nova página no Notion com blocos."""
    mock_client = MagicMock()
    mock_client.pages.create.return_value = {
        "id": "new-page-id-999",
        "url": "https://notion.so/new-page-id-999",
    }

    adapter = NotionAdapter(client=mock_client, inbox_database_id="db-inbox-123")
    note = Note(
        file_path=Path("./00-Inbox/Nova Ideia.md"),
        metadata=NoteMetadata(
            title="Nova Ideia",
            tags=["brain", "mvp"],
            category=ParaCategory.INBOX,
            summary="Uma nota recém criada.",
            privacy=PrivacyLevel.PRIVATE,
        ),
        content="# Título\n\nConteúdo explicativo da nota.",
    )

    result = adapter.create_page(note)

    assert result["id"] == "new-page-id-999"
    assert note.metadata.extra["notion_page_id"] == "new-page-id-999"
    assert note.metadata.extra["notion_url"] == "https://notion.so/new-page-id-999"
    mock_client.pages.create.assert_called_once()


def test_create_page_update_existing_note() -> None:
    """Testa a atualização de uma página do Notion caso já contenha notion_page_id no extra."""
    mock_client = MagicMock()
    mock_client.pages.update.return_value = {
        "id": "existing-page-id-888",
        "url": "https://notion.so/existing-page-id-888",
    }

    adapter = NotionAdapter(client=mock_client, inbox_database_id="db-inbox-123")
    note = Note(
        file_path=Path("./01-Projects/Projeto Atualizado.md"),
        metadata=NoteMetadata(
            title="Projeto Atualizado",
            tags=["update"],
            category=ParaCategory.PROJECTS,
            extra={"notion_page_id": "existing-page-id-888"},
        ),
        content="Conteúdo",
    )

    result = adapter.create_page(note)

    assert result["id"] == "existing-page-id-888"
    mock_client.pages.update.assert_called_once()
    mock_client.pages.create.assert_not_called()
