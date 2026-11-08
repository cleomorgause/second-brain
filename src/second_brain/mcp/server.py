"""Servidor MCP (Model Context Protocol) para integração com o Second Brain."""

from typing import Any

from mcp.server.mcpserver import MCPServer

from second_brain.adapters.obsidian import ObsidianVaultAdapter
from second_brain.config import settings
from second_brain.core.models import ParaCategory
from second_brain.services.ai_triage import AITriageService


def create_mcp_server(
    adapter: ObsidianVaultAdapter | None = None,
    triage_service: AITriageService | None = None,
) -> MCPServer:
    """Cria e configura uma instância do servidor MCP com as ferramentas do Second Brain."""
    vault_adapter = adapter or ObsidianVaultAdapter(settings.resolved_vault_path)
    ai_service = triage_service or AITriageService()

    server = MCPServer(
        name="second-brain",
        description="Servidor MCP local para gerenciamento e triagem do Segundo Cérebro (Obsidian)",
        version="0.1.0",
    )

    @server.tool()
    def capture_note(
        title: str,
        content: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Captura uma nova anotação rápida e a salva na caixa de entrada (00-Inbox).

        Args:
            title: Título ou assunto principal da anotação.
            content: Conteúdo em Markdown da anotação.
            tags: Lista opcional de tags sem o caractere '#'.

        Returns:
            Mensagem descritiva de confirmação com o arquivo gerado.
        """
        vault_adapter.initialize_vault_structure()
        cleaned_tags = [t.strip().lstrip("#") for t in (tags or []) if t.strip()]
        note = vault_adapter.create_inbox_note(
            title=title,
            content=content,
            tags=cleaned_tags,
        )
        return (
            f"Nota '{note.metadata.title}' capturada com sucesso na Inbox ({note.file_path.name})."
        )

    @server.tool()
    def list_notes(
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista anotações do cofre, opcionalmente filtrando por categoria P.A.R.A.

        Args:
            category: Categoria opcional para filtrar ('Inbox', 'Projects', 'Areas', 'Resources', 'Archive').
                      Caso omitido, retorna todas as notas de todas as categorias.

        Returns:
            Lista de dicionários contendo os metadados resumidos das notas.
        """
        vault_adapter.initialize_vault_structure()

        if category:
            normalized = category.strip().lower()
            matching_categories = [
                c
                for c in ParaCategory
                if normalized in c.value.lower() or normalized in c.name.lower()
            ]
            if not matching_categories:
                return [
                    {
                        "error": (
                            f"Categoria '{category}' inválida. Use uma das opções P.A.R.A.: "
                            f"{', '.join(c.value for c in ParaCategory)}"
                        )
                    }
                ]
            target_category = matching_categories[0]
            notes = vault_adapter.list_notes_in_category(target_category)
        else:
            notes = vault_adapter.list_all_notes()

        results: list[dict[str, Any]] = []
        for note in notes:
            results.append(
                {
                    "title": note.metadata.title,
                    "category": note.metadata.category.value,
                    "tags": note.metadata.tags,
                    "privacy": note.metadata.privacy.value,
                    "summary": note.metadata.summary,
                    "ai_processed": note.metadata.ai_processed,
                    "file_name": note.file_path.name,
                    "updated_at": note.metadata.updated_at.isoformat(),
                }
            )
        return results

    @server.tool()
    def read_note(
        title: str,
    ) -> dict[str, Any]:
        """Lê o conteúdo completo e todos os metadados de uma anotação específica pelo título.

        Args:
            title: Título da nota ou nome do arquivo (com ou sem extensão .md).

        Returns:
            Dicionário com conteúdo Markdown e metadados, ou mensagem de erro se não encontrada.
        """
        vault_adapter.initialize_vault_structure()
        note = vault_adapter.find_note_by_title(title)

        if not note:
            return {"error": f"Nota com título ou arquivo '{title}' não foi encontrada no cofre."}

        return {
            "title": note.metadata.title,
            "category": note.metadata.category.value,
            "tags": note.metadata.tags,
            "privacy": note.metadata.privacy.value,
            "created_at": note.metadata.created_at.isoformat(),
            "updated_at": note.metadata.updated_at.isoformat(),
            "summary": note.metadata.summary,
            "ai_processed": note.metadata.ai_processed,
            "extra": note.metadata.extra,
            "file_path": str(note.file_path),
            "content": note.content,
        }

    @server.tool()
    def triage_inbox() -> list[dict[str, Any]]:
        """Executa a triagem com Inteligência Artificial em todas as notas pendentes na Inbox.

        Analisa cada nota da pasta 00-Inbox com o LLM configurado, define a categoria P.A.R.A.
        mais adequada, gera resumo, tags e itens de ação, e move a nota para a pasta correspondente.

        Returns:
            Lista com os detalhes e status da triagem de cada anotação processada.
        """
        vault_adapter.initialize_vault_structure()
        inbox_notes = vault_adapter.list_notes_in_category(ParaCategory.INBOX)

        if not inbox_notes:
            return []

        triage_reports: list[dict[str, Any]] = []

        for note in inbox_notes:
            original_title = note.metadata.title
            try:
                result = ai_service.triage_note(note)

                # Atualiza metadados com as sugestões da IA
                note.metadata.title = result.suggested_title
                combined_tags = sorted(set(note.metadata.tags + result.suggested_tags))
                note.metadata.tags = combined_tags
                note.metadata.summary = result.summary
                note.metadata.ai_processed = True

                # Move a nota para o diretório P.A.R.A. de destino
                vault_adapter.move_note(
                    note=note,
                    target_category=result.suggested_category,
                    new_filename=result.suggested_title,
                )

                triage_reports.append(
                    {
                        "status": "success",
                        "original_title": original_title,
                        "suggested_title": result.suggested_title,
                        "category": result.suggested_category.value,
                        "tags": combined_tags,
                        "summary": result.summary,
                        "reasoning": result.reasoning,
                        "action_items": result.action_items,
                    }
                )
            except Exception as exc:
                triage_reports.append(
                    {
                        "status": "error",
                        "original_title": original_title,
                        "error": str(exc),
                    }
                )

        return triage_reports

    return server


# Instância padrão pré-configurada para uso geral e execução de servidor
mcp_server = create_mcp_server()


if __name__ == "__main__":
    mcp_server.run(transport="stdio")
