"""Testes para o adaptador do Obsidian e gerenciamento P.A.R.A."""

from pathlib import Path

from second_brain.adapters.obsidian import ObsidianVaultAdapter
from second_brain.core.models import ParaCategory, PrivacyLevel


def test_initialize_vault_structure(tmp_path: Path) -> None:
    """Verifica se todas as 5 pastas P.A.R.A. são criadas corretamente."""
    adapter = ObsidianVaultAdapter(tmp_path)
    created = adapter.initialize_vault_structure()

    assert len(created) == 5
    for category in ParaCategory:
        expected_dir = tmp_path / category.value
        assert expected_dir.exists()
        assert expected_dir.is_dir()


def test_create_and_parse_inbox_note(tmp_path: Path) -> None:
    """Testa criação de nota rápida na Inbox e a extração fiel do YAML frontmatter."""
    adapter = ObsidianVaultAdapter(tmp_path)
    adapter.initialize_vault_structure()

    note = adapter.create_inbox_note(
        title="Estudo sobre Model Context Protocol",
        content="O protocolo MCP padroniza como assistentes de IA acessam ferramentas externas.",
        tags=["ia", "mcp", "estudos"],
        privacy=PrivacyLevel.PRIVATE,
    )

    assert note.file_path.exists()
    assert note.metadata.category == ParaCategory.INBOX
    assert note.metadata.tags == ["ia", "mcp", "estudos"]

    # Re-parse a partir do arquivo salvo no disco
    parsed = adapter.parse_note(note.file_path)
    assert parsed.metadata.title == "Estudo sobre Model Context Protocol"
    assert parsed.metadata.privacy == PrivacyLevel.PRIVATE
    assert "MCP padroniza" in parsed.content


def test_move_note_between_categories(tmp_path: Path) -> None:
    """Testa a movimentação de uma nota da Inbox para a pasta de Recursos (Resources)."""
    adapter = ObsidianVaultAdapter(tmp_path)
    adapter.initialize_vault_structure()

    note = adapter.create_inbox_note(
        title="Referência Rápida de Python",
        content="Dicas de tipagem estática com mypy e pydantic.",
    )

    old_path = note.file_path
    assert old_path.exists()

    moved_note = adapter.move_note(
        note=note,
        target_category=ParaCategory.RESOURCES,
        new_filename="Guia de Tipagem Python",
    )

    assert not old_path.exists()  # Arquivo antigo na Inbox removido
    assert moved_note.file_path.exists()
    assert moved_note.file_path.parent.name == ParaCategory.RESOURCES.value
    assert moved_note.metadata.category == ParaCategory.RESOURCES
