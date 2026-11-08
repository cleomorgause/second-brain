"""Adaptadores de armazenamento e integrações externas (Obsidian, Notion)."""

from second_brain.adapters.notion import NotionAdapter
from second_brain.adapters.obsidian import ObsidianVaultAdapter

__all__ = ["NotionAdapter", "ObsidianVaultAdapter"]
