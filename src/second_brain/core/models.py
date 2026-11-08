"""Modelos de dados centrais para o Second Brain."""

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PrivacyLevel(StrEnum):
    """Nível de privacidade para controle de versionamento e sincronização."""

    PUBLIC = "public"
    PRIVATE = "private"


class ParaCategory(StrEnum):
    """Categorias da metodologia P.A.R.A."""

    INBOX = "00-Inbox"
    PROJECTS = "01-Projects"
    AREAS = "02-Areas"
    RESOURCES = "03-Resources"
    ARCHIVE = "04-Archive"


class NoteMetadata(BaseModel):
    """Metadados salvos no frontmatter YAML da nota."""

    title: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tags: list[str] = Field(default_factory=list)
    privacy: PrivacyLevel = PrivacyLevel.PRIVATE
    category: ParaCategory = ParaCategory.INBOX
    summary: str = ""
    ai_processed: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class Note(BaseModel):
    """Representação unificada de uma nota no Segundo Cérebro."""

    file_path: Path
    metadata: NoteMetadata
    content: str

    @property
    def filename(self) -> str:
        """Nome do arquivo da nota."""
        return self.file_path.name


class TriageResult(BaseModel):
    """Resultado estruturado gerado pelo assistente de IA ao analisar uma nota."""

    suggested_title: str
    suggested_category: ParaCategory
    suggested_tags: list[str] = Field(default_factory=list)
    summary: str
    reasoning: str
    action_items: list[str] = Field(default_factory=list)
