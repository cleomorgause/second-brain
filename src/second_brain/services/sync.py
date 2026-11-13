"""Serviço de sincronização unificada entre Obsidian e Notion."""

from enum import StrEnum

from pydantic import BaseModel, Field

from second_brain.adapters.notion import NotionAdapter
from second_brain.adapters.obsidian import ObsidianVaultAdapter, slugify_to_kebab_case
from second_brain.config import settings
from second_brain.core.models import Note, ParaCategory


class SyncDirection(StrEnum):
    """Direções suportadas para a sincronização de anotações."""

    BIDIRECTIONAL = "bidirectional"
    NOTION_TO_OBSIDIAN = "notion_to_obsidian"
    OBSIDIAN_TO_NOTION = "obsidian_to_notion"


class SyncReport(BaseModel):
    """Relatório estruturado com as operações realizadas durante a sincronização."""

    direction: SyncDirection
    obsidian_to_notion_created: int = 0
    obsidian_to_notion_updated: int = 0
    notion_to_obsidian_created: int = 0
    notion_to_obsidian_updated: int = 0
    errors: list[str] = Field(default_factory=list)

    @property
    def total_synced(self) -> int:
        """Soma total de notas criadas ou atualizadas nos dois sentidos."""
        return (
            self.obsidian_to_notion_created
            + self.obsidian_to_notion_updated
            + self.notion_to_obsidian_created
            + self.notion_to_obsidian_updated
        )


class SyncService:
    """Orquestra a sincronização de anotações entre o cofre local Obsidian e o Notion."""

    def __init__(
        self,
        obsidian_adapter: ObsidianVaultAdapter | None = None,
        notion_adapter: NotionAdapter | None = None,
    ) -> None:
        self.obsidian = obsidian_adapter or ObsidianVaultAdapter(settings.resolved_vault_path)
        self.notion = notion_adapter or NotionAdapter()

    def sync_inbox(self, direction: SyncDirection = SyncDirection.BIDIRECTIONAL) -> SyncReport:
        """Sincroniza as anotações da caixa de entrada (Inbox) conforme a direção especificada."""
        report = SyncReport(direction=direction)
        self.obsidian.initialize_vault_structure()

        # 1. Sincroniza Notion -> Obsidian
        if direction in (SyncDirection.BIDIRECTIONAL, SyncDirection.NOTION_TO_OBSIDIAN):
            self._sync_notion_to_obsidian(report)

        # 2. Sincroniza Obsidian -> Notion
        if direction in (SyncDirection.BIDIRECTIONAL, SyncDirection.OBSIDIAN_TO_NOTION):
            self._sync_obsidian_to_notion(report)

        return report

    def _sync_notion_to_obsidian(self, report: SyncReport) -> None:
        """Busca páginas na Inbox do Notion e as reflete como notas no Obsidian."""
        try:
            notion_notes = self.notion.fetch_inbox_pages()
        except Exception as exc:
            report.errors.append(f"Falha ao consultar Inbox do Notion: {exc}")
            return

        inbox_dir = self.obsidian.get_category_path(ParaCategory.INBOX)
        local_notes = self.obsidian.list_all_notes()

        # Mapeia notas locais por ID do Notion e por título
        local_by_notion_id: dict[str, Note] = {}
        local_by_title: dict[str, Note] = {}
        for note in local_notes:
            page_id = note.metadata.extra.get("notion_page_id")
            if page_id:
                local_by_notion_id[str(page_id)] = note
            local_by_title[note.metadata.title.strip().lower()] = note

        for n_note in notion_notes:
            notion_id = str(n_note.metadata.extra.get("notion_page_id", ""))
            clean_title = n_note.metadata.title.strip()
            norm_title = clean_title.lower()

            try:
                # Verifica se a nota já existe localmente
                existing_note = local_by_notion_id.get(notion_id) or local_by_title.get(norm_title)

                if existing_note:
                    # Atualiza nota local mantendo o caminho existente
                    existing_note.metadata.summary = n_note.metadata.summary
                    existing_note.metadata.tags = list(
                        set(existing_note.metadata.tags + n_note.metadata.tags)
                    )
                    existing_note.metadata.extra["notion_page_id"] = notion_id
                    if "notion_url" in n_note.metadata.extra:
                        existing_note.metadata.extra["notion_url"] = n_note.metadata.extra[
                            "notion_url"
                        ]
                    if n_note.content and not existing_note.content:
                        existing_note.content = n_note.content

                    self.obsidian.save_note(existing_note)
                    report.notion_to_obsidian_updated += 1
                else:
                    # Cria nova nota no Obsidian com nome seguro em kebab-case
                    safe_filename = slugify_to_kebab_case(clean_title)
                    file_path = inbox_dir / f"{safe_filename or 'nota-notion'}.md"

                    new_note = Note(
                        file_path=file_path,
                        metadata=n_note.metadata,
                        content=n_note.content,
                    )
                    self.obsidian.save_note(new_note)
                    report.notion_to_obsidian_created += 1
            except Exception as exc:
                report.errors.append(f"Erro ao salvar nota '{clean_title}' no Obsidian: {exc}")

    def _sync_obsidian_to_notion(self, report: SyncReport) -> None:
        """Pega as notas da Inbox local do Obsidian e as envia para o Notion."""
        try:
            inbox_notes = self.obsidian.list_notes_in_category(ParaCategory.INBOX)
        except Exception as exc:
            report.errors.append(f"Falha ao listar notas da Inbox local: {exc}")
            return

        for o_note in inbox_notes:
            title = o_note.metadata.title
            has_notion_id = bool(o_note.metadata.extra.get("notion_page_id"))

            try:
                self.notion.create_page(o_note)
                # Salva novamente no Obsidian para persistir o novo 'notion_page_id' no YAML
                self.obsidian.save_note(o_note)

                if has_notion_id:
                    report.obsidian_to_notion_updated += 1
                else:
                    report.obsidian_to_notion_created += 1
            except Exception as exc:
                report.errors.append(f"Erro ao sincronizar '{title}' para o Notion: {exc}")
