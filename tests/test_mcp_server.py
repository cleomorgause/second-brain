"""Testes para o servidor MCP local do Second Brain."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from mcp.types import CallToolResult
from typer.testing import CliRunner

from second_brain.adapters.obsidian import ObsidianVaultAdapter
from second_brain.cli import app
from second_brain.core.models import ParaCategory, TriageResult
from second_brain.mcp.server import create_mcp_server


@pytest.fixture
def anyio_backend() -> str:
    """Fixa o backend assíncrono exclusivamente no asyncio para evitar testes duplicados e lentidão."""
    return "asyncio"


@pytest.fixture
def temp_vault(tmp_path: Path) -> ObsidianVaultAdapter:
    """Fixture que fornece um ObsidianVaultAdapter isolado para testes."""
    adapter = ObsidianVaultAdapter(vault_path=tmp_path)
    adapter.initialize_vault_structure()
    return adapter


@pytest.fixture
def mock_triage_service() -> MagicMock:
    """Fixture com um serviço de triagem simulado."""
    service = MagicMock()
    service.triage_note.return_value = TriageResult(
        suggested_title="Projeto IA Second Brain",
        suggested_category=ParaCategory.PROJECTS,
        suggested_tags=["ai", "python"],
        summary="Desenvolvimento de um assistente de segundo cérebro.",
        reasoning="Possui objetivo claro e executável.",
        action_items=["Implementar servidor MCP", "Testar ferramentas"],
    )
    return service


@pytest.mark.anyio
async def test_mcp_capture_note(temp_vault: ObsidianVaultAdapter) -> None:
    """Testa se a ferramenta capture_note salva a anotação na Inbox corretamente."""
    server = create_mcp_server(adapter=temp_vault)

    result = await server.call_tool(
        "capture_note",
        {
            "title": "Primeira Ideia MCP",
            "content": "Conteúdo teste para MCP.",
            "tags": ["#teste", "mcp"],
        },
    )

    assert isinstance(result, CallToolResult)
    assert result.is_error is False
    assert "Primeira Ideia MCP" in str(result.content)

    inbox_notes = temp_vault.list_notes_in_category(ParaCategory.INBOX)
    assert len(inbox_notes) == 1
    assert inbox_notes[0].metadata.title == "Primeira Ideia MCP"
    assert inbox_notes[0].metadata.tags == ["teste", "mcp"]
    assert inbox_notes[0].content == "Conteúdo teste para MCP."


@pytest.mark.anyio
async def test_mcp_list_notes(temp_vault: ObsidianVaultAdapter) -> None:
    """Testa a listagem geral e filtrada por categoria no servidor MCP."""
    server = create_mcp_server(adapter=temp_vault)

    # Cria notas em categorias diferentes
    note_inbox = temp_vault.create_inbox_note("Nota Inbox", "Texto Inbox", tags=["rapido"])
    temp_vault.move_note(note_inbox, ParaCategory.RESOURCES, new_filename="Recurso Importante")
    temp_vault.create_inbox_note("Outra Inbox", "Texto Outra")

    # Lista todas
    all_res = await server.call_tool("list_notes", {})
    assert isinstance(all_res, CallToolResult)
    assert all_res.is_error is False
    assert all_res.structured_content is not None
    structured_all: list[dict[str, Any]] = all_res.structured_content["result"]
    assert len(structured_all) == 2

    # Lista filtrando por categoria válida
    resources_res = await server.call_tool("list_notes", {"category": "Resources"})
    assert isinstance(resources_res, CallToolResult)
    assert resources_res.is_error is False
    assert resources_res.structured_content is not None
    structured_resources: list[dict[str, Any]] = resources_res.structured_content["result"]
    assert len(structured_resources) == 1
    assert structured_resources[0]["title"] == "Nota Inbox"
    assert structured_resources[0]["category"] == ParaCategory.RESOURCES.value

    # Lista filtrando por categoria inexistente
    invalid_res = await server.call_tool("list_notes", {"category": "Inexistente"})
    assert isinstance(invalid_res, CallToolResult)
    assert invalid_res.is_error is False
    assert invalid_res.structured_content is not None
    structured_invalid: list[dict[str, Any]] = invalid_res.structured_content["result"]
    assert "error" in structured_invalid[0]


@pytest.mark.anyio
async def test_mcp_read_note(temp_vault: ObsidianVaultAdapter) -> None:
    """Testa a leitura de uma anotação pelo título ou nome de arquivo."""
    server = create_mcp_server(adapter=temp_vault)

    temp_vault.create_inbox_note(
        title="Guia de Estudos Python",
        content="## Tópicos:\n- Tipagem estrita\n- FastMCP/MCPServer",
        tags=["estudo", "python"],
    )

    # Leitura com sucesso pelo título
    read_res = await server.call_tool("read_note", {"title": "Guia de Estudos Python"})
    assert isinstance(read_res, CallToolResult)
    assert read_res.is_error is False
    assert read_res.structured_content is not None
    data: dict[str, Any] = dict(read_res.structured_content)
    assert data["title"] == "Guia de Estudos Python"
    assert "FastMCP/MCPServer" in data["content"]
    assert "estudo" in data["tags"]

    # Leitura com sucesso com extensão .md
    read_md_res = await server.call_tool("read_note", {"title": "Guia de Estudos Python.md"})
    assert isinstance(read_md_res, CallToolResult)
    assert read_md_res.is_error is False
    assert read_md_res.structured_content is not None
    data_md: dict[str, Any] = dict(read_md_res.structured_content)
    assert data_md["title"] == "Guia de Estudos Python"

    # Leitura de nota inexistente
    missing_res = await server.call_tool("read_note", {"title": "Nota Que Nao Existe"})
    assert isinstance(missing_res, CallToolResult)
    assert missing_res.is_error is False
    assert missing_res.structured_content is not None
    missing_data: dict[str, Any] = dict(missing_res.structured_content)
    assert "error" in missing_data


@pytest.mark.anyio
async def test_mcp_triage_inbox(
    temp_vault: ObsidianVaultAdapter, mock_triage_service: MagicMock
) -> None:
    """Testa o processo de triagem automática com IA via ferramenta MCP."""
    server = create_mcp_server(adapter=temp_vault, triage_service=mock_triage_service)

    # Triagem com Inbox vazia
    empty_res = await server.call_tool("triage_inbox", {})
    assert isinstance(empty_res, CallToolResult)
    assert empty_res.is_error is False
    assert empty_res.structured_content is not None
    assert empty_res.structured_content["result"] == []

    # Cria uma nota bruta na Inbox
    temp_vault.create_inbox_note(
        title="segundo cerebro mcp",
        content="fazer servidor mcp usando mcp 2.x e python",
        tags=["brain"],
    )

    # Executa a triagem
    triage_res = await server.call_tool("triage_inbox", {})
    assert isinstance(triage_res, CallToolResult)
    assert triage_res.is_error is False
    assert triage_res.structured_content is not None
    reports: list[dict[str, Any]] = triage_res.structured_content["result"]
    assert len(reports) == 1
    assert reports[0]["status"] == "success"
    assert reports[0]["suggested_title"] == "Projeto IA Second Brain"
    assert reports[0]["category"] == ParaCategory.PROJECTS.value

    # Confirma que a Inbox agora está vazia e a nota foi para Projects
    assert len(temp_vault.list_notes_in_category(ParaCategory.INBOX)) == 0
    projects_notes = temp_vault.list_notes_in_category(ParaCategory.PROJECTS)
    assert len(projects_notes) == 1
    assert projects_notes[0].metadata.title == "Projeto IA Second Brain"
    assert projects_notes[0].metadata.ai_processed is True


def test_cli_mcp_serve_help() -> None:
    """Verifica se o comando CLI 'brain mcp-serve' está registrado com parâmetros corretos."""
    runner = CliRunner()
    result = runner.invoke(app, ["mcp-serve", "--help"])
    assert result.exit_code == 0
    assert "--transport" in result.output
    assert "--host" in result.output
    assert "--port" in result.output
