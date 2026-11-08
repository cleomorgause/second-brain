"""Interface de Linha de Comando (CLI) para o Second Brain."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from second_brain.adapters.obsidian import ObsidianVaultAdapter
from second_brain.config import settings
from second_brain.core.models import ParaCategory
from second_brain.services.ai_triage import AITriageService

app = typer.Typer(
    name="brain",
    help="Assistente inteligente de Segundo Cérebro para Obsidian e Notion.",
    add_completion=False,
)
console = Console()


def get_adapter() -> ObsidianVaultAdapter:
    """Retorna o adaptador do cofre configurado."""
    return ObsidianVaultAdapter(settings.resolved_vault_path)


@app.command()
def init() -> None:
    """Inicializa a estrutura de pastas P.A.R.A. no cofre do Obsidian."""
    adapter = get_adapter()
    console.print(f"[bold cyan]Inicializando cofre em:[/bold cyan] {adapter.vault_path}")
    created = adapter.initialize_vault_structure()

    if created:
        console.print("[green]Pastas P.A.R.A. criadas com sucesso:[/green]")
        for d in created:
            console.print(f"  • [yellow]{d.name}[/yellow]")
    else:
        console.print("[green]A estrutura de pastas P.A.R.A. já está configurada e pronta![/green]")


@app.command()
def capture(
    title: str = typer.Argument(..., help="Título ou assunto rápido da nota"),
    content: str = typer.Option("", "--content", "-c", help="Conteúdo detalhado da nota"),
    tags: str | None = typer.Option(None, "--tags", "-t", help="Tags separadas por vírgula"),
) -> None:
    """Captura uma nota rápida para a caixa de entrada (00-Inbox)."""
    adapter = get_adapter()
    adapter.initialize_vault_structure()

    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    note = adapter.create_inbox_note(title=title, content=content, tags=tag_list)

    console.print(
        Panel(
            f"[bold green]Nota capturada com sucesso na Inbox![/bold green]\n"
            f"[cyan]Arquivo:[/cyan] {note.file_path.name}\n"
            f"[cyan]Caminho:[/cyan] {note.file_path}",
            title="📥 Second Brain Inbox",
        )
    )


@app.command(name="list")
def list_notes(
    category: str | None = typer.Option(
        None,
        "--category",
        "-c",
        help="Filtrar por categoria (Inbox, Projects, Areas, Resources, Archive)",
    ),
) -> None:
    """Lista as notas organizadas pelas categorias P.A.R.A."""
    adapter = get_adapter()

    categories_to_show = []
    if category:
        matching = [c for c in ParaCategory if category.lower() in c.value.lower()]
        if not matching:
            console.print(f"[red]Categoria '{category}' não encontrada.[/red]")
            raise typer.Exit(1)
        categories_to_show = matching
    else:
        categories_to_show = list(ParaCategory)

    table = Table(
        title="🧠 Notas no Segundo Cérebro", show_header=True, header_style="bold magenta"
    )
    table.add_column("Categoria", style="cyan", width=18)
    table.add_column("Título", style="white")
    table.add_column("Tags", style="yellow")
    table.add_column("Status IA", style="green")

    total_notes = 0
    for cat in categories_to_show:
        notes = adapter.list_notes_in_category(cat)
        for note in notes:
            total_notes += 1
            tags_str = ", ".join(note.metadata.tags) if note.metadata.tags else "-"
            ai_status = "Processada" if note.metadata.ai_processed else "Pendente"
            table.add_row(cat.value, note.metadata.title, tags_str, ai_status)

    if total_notes == 0:
        console.print("[yellow]Nenhuma nota encontrada no cofre.[/yellow]")
    else:
        console.print(table)


@app.command()
def triage(
    model: str | None = typer.Option(
        None, "--model", "-m", help="Substituir modelo padrão de IA para esta execução"
    ),
) -> None:
    """Usa IA para processar as notas pendentes na Inbox e sugerir organização P.A.R.A."""
    adapter = get_adapter()
    inbox_notes = adapter.list_notes_in_category(ParaCategory.INBOX)

    if not inbox_notes:
        console.print(
            "[green]🎉 Sua Inbox está limpa! Nenhuma nota pendente para organizar.[/green]"
        )
        return

    console.print(f"[bold cyan]Encontradas {len(inbox_notes)} nota(s) na Inbox.[/bold cyan]")
    triage_service = AITriageService(model_name=model)

    for note in inbox_notes:
        console.print(f"\n[bold]Processando nota:[/bold] [yellow]{note.metadata.title}[/yellow]")

        try:
            with console.status(
                "[bold cyan]Conectando ao modelo de IA...[/bold cyan]", spinner="dots"
            ) as status:

                def update_status(msg: str) -> None:
                    status.update(f"[cyan]{msg}[/cyan]")

                result = triage_service.triage_note(note, status_callback=update_status)
        except Exception as e:
            console.print(f"[red]Erro ao processar com a IA: {e}[/red]")
            continue

        panel_content = (
            f"[bold]Título Sugerido:[/bold] {result.suggested_title}\n"
            f"[bold]Categoria Sugerida:[/bold] [cyan]{result.suggested_category.value}[/cyan]\n"
            f"[bold]Tags:[/bold] {', '.join(result.suggested_tags)}\n"
            f"[bold]Resumo:[/bold] {result.summary}\n"
            f"[bold]Justificativa:[/bold] {result.reasoning}"
        )
        if result.action_items:
            panel_content += "\n[bold]Ações Identificadas:[/bold]\n" + "\n".join(
                f"  • [green]{item}[/green]" for item in result.action_items
            )

        console.print(Panel(panel_content, title=f"🤖 Sugestão da IA para: {note.filename}"))

        should_apply = Confirm.ask("Deseja aplicar a organização sugerida e mover a nota?")
        if should_apply:
            note.metadata.title = result.suggested_title
            note.metadata.tags = list(set(note.metadata.tags + result.suggested_tags))
            note.metadata.summary = result.summary
            note.metadata.ai_processed = True

            adapter.move_note(
                note=note,
                target_category=result.suggested_category,
                new_filename=result.suggested_title,
            )
            console.print(
                f"[green]✔ Nota movida com sucesso para {result.suggested_category.value}![/green]"
            )
        else:
            console.print("[yellow]Nota mantida na Inbox sem alterações.[/yellow]")


@app.command()
def status() -> None:
    """Exibe o diagnóstico do ambiente, chaves detectadas e caminhos configurados."""
    table = Table(title="⚙ Diagnóstico do Second Brain", show_header=True)
    table.add_column("Configuração", style="cyan")
    table.add_column("Valor / Estado", style="white")

    table.add_row("Cofre Obsidian", str(settings.resolved_vault_path))
    table.add_row("Modelo de IA Padrão", settings.default_ai_model)
    table.add_row(
        "Chave Gemini",
        "[green]Configurada[/green]" if settings.gemini_api_key else "[red]Ausente[/red]",
    )
    table.add_row(
        "Chave OpenAI",
        "[green]Configurada[/green]" if settings.openai_api_key else "[yellow]Opcional[/yellow]",
    )
    table.add_row(
        "Chave Claude",
        "[green]Configurada[/green]" if settings.anthropic_api_key else "[yellow]Opcional[/yellow]",
    )
    table.add_row(
        "Notion API Key",
        "[green]Configurada[/green]"
        if settings.notion_api_key
        else "[yellow]Pendente (Fase 2)[/yellow]",
    )

    console.print(table)


@app.command(name="mcp-serve")
def mcp_serve(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="Tipo de transporte do MCP: 'stdio' ou 'sse'",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host para binding no transporte SSE",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Porta para binding no transporte SSE",
    ),
) -> None:
    """Inicia o servidor MCP local para integração com Claude Desktop, Cursor e outros clientes."""
    from second_brain.mcp.server import mcp_server

    normalized_transport = transport.strip().lower()
    stderr_console = Console(stderr=True)

    if normalized_transport == "stdio":
        stderr_console.print("[cyan]Iniciando servidor MCP do Second Brain via stdio...[/cyan]")
        mcp_server.run(transport="stdio")
    elif normalized_transport == "sse":
        stderr_console.print(
            f"[cyan]Iniciando servidor MCP do Second Brain via SSE em http://{host}:{port}...[/cyan]"
        )
        mcp_server.run(transport="sse", host=host, port=port)
    else:
        stderr_console.print(
            f"[red]Transporte desconhecido: '{transport}'. Escolha 'stdio' ou 'sse'.[/red]"
        )
        raise typer.Exit(code=1)


@app.command(name="sync")
def sync(
    direction: str = typer.Option(
        "bidirectional",
        "--direction",
        "-d",
        help="Direção da sincronização: 'bidirectional', 'notion-to-obsidian', 'obsidian-to-notion'",
    ),
) -> None:
    """Sincroniza as notas da Inbox entre o cofre Obsidian local e a base do Notion."""
    from second_brain.services.sync import SyncDirection, SyncService

    normalized_dir = direction.strip().lower().replace("-", "_")
    valid_directions = {d.value: d for d in SyncDirection}

    if normalized_dir not in valid_directions:
        console.print(
            f"[red]Direção inválida: '{direction}'. "
            f"Opções válidas: {', '.join(valid_directions.keys())}[/red]"
        )
        raise typer.Exit(code=1)

    target_dir = valid_directions[normalized_dir]
    console.print(
        f"[bold cyan]Iniciando sincronização da Inbox ({target_dir.value})...[/bold cyan]"
    )

    sync_service = SyncService()
    report = sync_service.sync_inbox(direction=target_dir)

    console.print(
        f"[green]✔ Sincronização concluída! Total processado: {report.total_synced}[/green]"
    )
    console.print(
        f"  • Notion ➔ Obsidian criadas: [yellow]{report.notion_to_obsidian_created}[/yellow]"
    )
    console.print(
        f"  • Notion ➔ Obsidian atualizadas: [yellow]{report.notion_to_obsidian_updated}[/yellow]"
    )
    console.print(
        f"  • Obsidian ➔ Notion criadas: [yellow]{report.obsidian_to_notion_created}[/yellow]"
    )
    console.print(
        f"  • Obsidian ➔ Notion atualizadas: [yellow]{report.obsidian_to_notion_updated}[/yellow]"
    )

    if report.errors:
        console.print("\n[bold red]Avisos/Erros na sincronização:[/bold red]")
        for err in report.errors:
            console.print(f"  • [red]{err}[/red]")


if __name__ == "__main__":
    app()
