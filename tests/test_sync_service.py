"""Testes unitários para o serviço de sincronização unificada (SyncService)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from second_brain.adapters.notion import NotionAdapter
from second_brain.adapters.obsidian import ObsidianVaultAdapter
from second_brain.cli import app
from second_brain.core.models import Note, NoteMetadata, ParaCategory
from second_brain.services.sync import SyncDirection, SyncService


@pytest.fixture
def temp_vault(tmp_path: Path) -> ObsidianVaultAdapter:
    """Fixture com um cofre Obsidian temporário."""
    adapter = ObsidianVaultAdapter(vault_path=tmp_path)
    adapter.initialize_vault_structure()
    return adapter


def test_sync_notion_to_obsidian_creates_new_note(temp_vault: ObsidianVaultAdapter) -> None:
    """Testa a criação de uma nota local no Obsidian vinda do Notion."""
    mock_notion = MagicMock(spec=NotionAdapter)
    mock_notion.fetch_inbox_pages.return_value = [
        Note(
            file_path=Path("notion://page-abc"),
            metadata=NoteMetadata(
                title="Ideia do Notion",
                tags=["notion", "inbox"],
                category=ParaCategory.INBOX,
                summary="Nota capturada no Notion móvel.",
                extra={"notion_page_id": "page-abc"},
            ),
            content="Conteúdo vindo diretamente do Notion.",
        )
    ]

    service = SyncService(obsidian_adapter=temp_vault, notion_adapter=mock_notion)
    report = service.sync_inbox(direction=SyncDirection.NOTION_TO_OBSIDIAN)

    assert report.notion_to_obsidian_created == 1
    assert report.notion_to_obsidian_updated == 0
    assert len(report.errors) == 0

    local_notes = temp_vault.list_notes_in_category(ParaCategory.INBOX)
    assert len(local_notes) == 1
    assert local_notes[0].metadata.title == "Ideia do Notion"
    assert local_notes[0].metadata.extra["notion_page_id"] == "page-abc"
    assert local_notes[0].content == "Conteúdo vindo diretamente do Notion."


def test_sync_notion_to_obsidian_updates_existing_note(temp_vault: ObsidianVaultAdapter) -> None:
    """Testa a atualização de uma nota existente no Obsidian com dados do Notion."""
    # Cria nota local prévia
    local_note = temp_vault.create_inbox_note(
        title="Planejamento Semanal",
        content="Conteúdo inicial local.",
        tags=["planejamento"],
    )

    mock_notion = MagicMock(spec=NotionAdapter)
    mock_notion.fetch_inbox_pages.return_value = [
        Note(
            file_path=Path("notion://page-xyz"),
            metadata=NoteMetadata(
                title="Planejamento Semanal",
                tags=["produtividade"],
                category=ParaCategory.INBOX,
                summary="Resumo atualizado no Notion.",
                extra={"notion_page_id": "page-xyz"},
            ),
            content="",
        )
    ]

    service = SyncService(obsidian_adapter=temp_vault, notion_adapter=mock_notion)
    report = service.sync_inbox(direction=SyncDirection.NOTION_TO_OBSIDIAN)

    assert report.notion_to_obsidian_created == 0
    assert report.notion_to_obsidian_updated == 1

    updated_note = temp_vault.parse_note(local_note.file_path)
    assert updated_note.metadata.summary == "Resumo atualizado no Notion."
    assert "produtividade" in updated_note.metadata.tags
    assert "planejamento" in updated_note.metadata.tags
    assert updated_note.metadata.extra["notion_page_id"] == "page-xyz"


def test_sync_obsidian_to_notion_creates_and_links_page(temp_vault: ObsidianVaultAdapter) -> None:
    """Testa o envio de uma nota do Obsidian para o Notion e o salvamento do notion_page_id."""
    created_note = temp_vault.create_inbox_note(
        title="Nota Local para Sincronizar",
        content="Texto criado no Obsidian.",
        tags=["local"],
    )

    def fake_create_page(note: Note) -> dict[str, str]:
        note.metadata.extra["notion_page_id"] = "notion-generated-123"
        return {"id": "notion-generated-123"}

    mock_notion = MagicMock(spec=NotionAdapter)
    mock_notion.create_page.side_effect = fake_create_page

    service = SyncService(obsidian_adapter=temp_vault, notion_adapter=mock_notion)
    report = service.sync_inbox(direction=SyncDirection.OBSIDIAN_TO_NOTION)

    assert report.obsidian_to_notion_created == 1
    assert report.obsidian_to_notion_updated == 0

    reloaded_note = temp_vault.parse_note(created_note.file_path)
    assert reloaded_note.metadata.extra.get("notion_page_id") == "notion-generated-123"


def test_sync_inbox_handles_error_gracefully(temp_vault: ObsidianVaultAdapter) -> None:
    """Verifica se falhas de conexão ou autenticação são capturadas no relatório de erros."""
    mock_notion = MagicMock(spec=NotionAdapter)
    mock_notion.fetch_inbox_pages.side_effect = RuntimeError("Erro de conexão com API")

    service = SyncService(obsidian_adapter=temp_vault, notion_adapter=mock_notion)
    report = service.sync_inbox(direction=SyncDirection.NOTION_TO_OBSIDIAN)

    assert len(report.errors) == 1
    assert "Falha ao consultar Inbox do Notion" in report.errors[0]


def test_cli_sync_command_options() -> None:
    """Testa o comando CLI 'brain sync' com parâmetros válidos e inválidos."""
    runner = CliRunner()

    # Help
    help_res = runner.invoke(app, ["sync", "--help"])
    assert help_res.exit_code == 0
    assert "--direction" in help_res.output

    # Direção inválida
    inv_res = runner.invoke(app, ["sync", "--direction", "direcao_invalida"])
    assert inv_res.exit_code == 1
    assert "Direção inválida" in inv_res.output
