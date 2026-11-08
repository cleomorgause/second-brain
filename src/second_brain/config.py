"""Módulo de configuração baseado em Pydantic Settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais do sistema carregadas de variáveis de ambiente ou .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    vault_path: Path = Path("./my_vault")
    default_ai_model: str = "gemini/gemini-3.8-flash"

    # Chaves de API para os provedores suportados
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Configurações do Notion (para o MVP)
    notion_api_key: str | None = None
    notion_inbox_database_id: str | None = None

    @property
    def resolved_vault_path(self) -> Path:
        """Retorna o caminho do cofre devidamente resolvido no sistema de arquivos."""
        return self.vault_path.resolve()


settings = Settings()
