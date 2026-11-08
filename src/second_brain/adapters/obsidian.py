"""Adaptador para o cofre local do Obsidian em formato Markdown."""

import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from second_brain.core.models import Note, NoteMetadata, ParaCategory, PrivacyLevel

FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


class ObsidianVaultAdapter:
    """Gerencia a leitura, escrita e organização de arquivos no cofre do Obsidian."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path.resolve()

    def initialize_vault_structure(self) -> list[Path]:
        """Cria as pastas do padrão P.A.R.A. no cofre caso ainda não existam."""
        created_dirs: list[Path] = []
        for category in ParaCategory:
            dir_path = self.vault_path / category.value
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                created_dirs.append(dir_path)
        return created_dirs

    def get_category_path(self, category: ParaCategory) -> Path:
        """Retorna o diretório correspondente a uma categoria P.A.R.A."""
        return self.vault_path / category.value

    def parse_note(self, file_path: Path) -> Note:
        """Lê um arquivo Markdown e extrai o frontmatter YAML e o conteúdo."""
        text = file_path.read_text(encoding="utf-8")
        match = FRONTMATTER_PATTERN.match(text)

        if match:
            raw_yaml, content = match.groups()
            try:
                data = yaml.safe_load(raw_yaml) or {}
            except yaml.YAMLError:
                data = {}

            category_val = data.get("category", ParaCategory.INBOX.value)
            try:
                category = ParaCategory(category_val)
            except ValueError:
                category = ParaCategory.INBOX

            privacy_val = data.get("privacy", PrivacyLevel.PRIVATE.value)
            try:
                privacy = PrivacyLevel(privacy_val)
            except ValueError:
                privacy = PrivacyLevel.PRIVATE

            metadata = NoteMetadata(
                title=data.get("title", file_path.stem),
                created_at=data.get("created_at", datetime.now(UTC)),
                updated_at=data.get("updated_at", datetime.now(UTC)),
                tags=data.get("tags", []),
                privacy=privacy,
                category=category,
                summary=data.get("summary", ""),
                ai_processed=data.get("ai_processed", False),
                extra={
                    k: v
                    for k, v in data.items()
                    if k
                    not in {
                        "title",
                        "created_at",
                        "updated_at",
                        "tags",
                        "privacy",
                        "category",
                        "summary",
                        "ai_processed",
                    }
                },
            )
        else:
            # Nota sem frontmatter YAML
            metadata = NoteMetadata(
                title=file_path.stem,
                created_at=datetime.fromtimestamp(file_path.stat().st_ctime, tz=UTC),
                updated_at=datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC),
                privacy=PrivacyLevel.PRIVATE,
                category=ParaCategory.INBOX,
            )
            content = text

        return Note(
            file_path=file_path,
            metadata=metadata,
            content=content.strip(),
        )

    def save_note(self, note: Note) -> Path:
        """Salva a nota no disco serializando o frontmatter YAML e o conteúdo Markdown."""
        data = {
            "title": note.metadata.title,
            "created_at": note.metadata.created_at.isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "tags": note.metadata.tags,
            "privacy": note.metadata.privacy.value,
            "category": note.metadata.category.value,
            "summary": note.metadata.summary,
            "ai_processed": note.metadata.ai_processed,
            **note.metadata.extra,
        }

        yaml_str = yaml.dump(data, sort_keys=False, allow_unicode=True).strip()
        file_content = f"---\n{yaml_str}\n---\n\n{note.content}\n"

        note.file_path.parent.mkdir(parents=True, exist_ok=True)
        note.file_path.write_text(file_content, encoding="utf-8")
        return note.file_path

    def create_inbox_note(
        self,
        title: str,
        content: str,
        tags: list[str] | None = None,
        privacy: PrivacyLevel = PrivacyLevel.PRIVATE,
    ) -> Note:
        """Cria uma nova anotação rápida na Inbox."""
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
        filename = f"{safe_title}.md"
        inbox_dir = self.get_category_path(ParaCategory.INBOX)
        file_path = inbox_dir / filename

        metadata = NoteMetadata(
            title=title,
            tags=tags or [],
            privacy=privacy,
            category=ParaCategory.INBOX,
        )

        note = Note(file_path=file_path, metadata=metadata, content=content)
        self.save_note(note)
        return note

    def list_notes_in_category(self, category: ParaCategory) -> list[Note]:
        """Lista todas as notas dentro de uma categoria P.A.R.A."""
        category_dir = self.get_category_path(category)
        if not category_dir.exists():
            return []

        notes: list[Note] = []
        for file_path in category_dir.glob("*.md"):
            try:
                notes.append(self.parse_note(file_path))
            except Exception:
                continue
        return notes

    def list_all_notes(self) -> list[Note]:
        """Lista todas as notas de todas as categorias P.A.R.A. no cofre."""
        all_notes: list[Note] = []
        for category in ParaCategory:
            all_notes.extend(self.list_notes_in_category(category))
        return all_notes

    def find_note_by_title(self, title: str) -> Note | None:
        """Busca uma nota no cofre pelo título ou nome do arquivo (case-insensitive)."""
        normalized_query = title.strip().lower()
        if normalized_query.endswith(".md"):
            normalized_query = normalized_query[:-3]

        for note in self.list_all_notes():
            if (
                note.metadata.title.strip().lower() == normalized_query
                or note.file_path.stem.lower() == normalized_query
            ):
                return note
        return None

    def move_note(
        self, note: Note, target_category: ParaCategory, new_filename: str | None = None
    ) -> Note:
        """Move uma nota para outra categoria P.A.R.A. e atualiza seus metadados."""
        target_dir = self.get_category_path(target_category)
        target_dir.mkdir(parents=True, exist_ok=True)

        final_filename = new_filename if new_filename else note.file_path.name
        if not final_filename.endswith(".md"):
            final_filename += ".md"

        new_file_path = target_dir / final_filename

        # Remove o arquivo antigo se for diferente do novo
        if note.file_path.exists() and note.file_path.resolve() != new_file_path.resolve():
            note.file_path.unlink()

        note.file_path = new_file_path
        note.metadata.category = target_category
        self.save_note(note)
        return note
