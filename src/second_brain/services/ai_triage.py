"""Serviço de IA para triagem automática de notas e organização P.A.R.A."""

import json
import os
import re
from typing import Any

import litellm

from second_brain.config import settings
from second_brain.core.models import Note, ParaCategory, TriageResult

TRIAGE_SYSTEM_PROMPT = """Você é um assistente especialista em gestão de conhecimento pessoal e produtividade, utilizando a metodologia P.A.R.A. (Projects, Areas, Resources, Archive).

Sua tarefa é analisar uma anotação recente da Inbox do usuário e determinar:
1. Um título claro e descritivo.
2. A categoria P.A.R.A. mais adequada:
   - "01-Projects": Iniciativas com objetivo específico e prazo ou critérios de conclusão claros.
   - "02-Areas": Áreas contínuas de responsabilidade sem data de término (ex: Finanças, Saúde, Gestão de Carreira).
   - "03-Resources": Tópicos de interesse permanente, referências de estudo, tutoriais, anotações de livros/cursos ou mídias.
   - "04-Archive": Itens inativos, finalizados ou referências obsoletas.
3. Lista de 2 a 5 tags concisas e úteis (sem o caractere '#').
4. Um resumo em 1 ou 2 frases da essência do conteúdo.
5. Uma breve justificativa para a categoria escolhida.
6. Ações ou tarefas imediatas extraídas do texto (se houver).

Você DEVE responder ESTRITAMENTE em formato JSON com o seguinte esquema:
{
  "suggested_title": "string",
  "suggested_category": "01-Projects" | "02-Areas" | "03-Resources" | "04-Archive",
  "suggested_tags": ["tag1", "tag2"],
  "summary": "string",
  "reasoning": "string",
  "action_items": ["item 1", "item 2"]
}
"""


def parse_json_safely(raw_text: str) -> dict[str, Any]:
    """Extrai e valida JSON da resposta do modelo de forma tolerante a falhas comuns."""
    text = raw_text.strip()

    # Remove cercaduras de código Markdown (```json ... ```) se presentes
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Tenta parsing direto
    try:
        return dict(json.loads(text))
    except json.JSONDecodeError:
        pass

    # Tenta extrair o maior bloco delimitado por { e }
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        extracted = match.group(1)
        try:
            return dict(json.loads(extracted))
        except json.JSONDecodeError:
            # Substitui quebras de linha literais dentro de strings por espaços
            sanitized = re.sub(r"(?<!\\)\n", " ", extracted)
            try:
                return dict(json.loads(sanitized))
            except json.JSONDecodeError:
                pass

    raise ValueError(
        f"Não foi possível converter a resposta da IA em JSON válido. Texto retornado:\n{raw_text}"
    )


class AITriageService:
    """Gerencia a comunicação com modelos de IA (Gemini, Claude, GPT) via LiteLLM."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.default_ai_model
        self._configure_credentials()

    def _configure_credentials(self) -> None:
        """Injeta as credenciais de API no ambiente para o LiteLLM."""
        if settings.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    def triage_note(
        self,
        note: Note,
        status_callback: Any = None,
    ) -> TriageResult:
        """Analisa o conteúdo de uma nota e retorna o resultado estruturado da triagem."""
        if status_callback:
            status_callback(f"Preparando prompt e lendo nota '{note.metadata.title}'...")

        user_prompt = f"Título atual: {note.metadata.title}\n\nConteúdo da nota:\n{note.content}"

        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "timeout": 60.0,
            "max_tokens": 4096,
        }

        # Para Gemini 3+, não passamos temperature
        if "gemini-3" not in self.model_name.lower():
            kwargs["temperature"] = 0.2

        if status_callback:
            status_callback(f"Enviando para {self.model_name} (aguardando resposta da API)...")

        # Modelos de fallback caso o principal esteja sofrendo pico de demanda (503)
        fallback_models = []
        if "gemini-3.8-flash" in self.model_name:
            fallback_models = ["gemini/gemini-2.5-pro", "gemini/gemini-3.8-pro"]

        response = litellm.completion(
            fallbacks=fallback_models if fallback_models else None,
            num_retries=2,
            **kwargs,
        )

        if status_callback:
            status_callback("Resposta recebida da IA! Processando JSON e categorias P.A.R.A....")

        raw_content = response.choices[0].message.content or "{}"
        data = parse_json_safely(raw_content)

        raw_category = data.get("suggested_category", ParaCategory.RESOURCES.value)
        try:
            category = ParaCategory(raw_category)
        except ValueError:
            category = ParaCategory.RESOURCES

        return TriageResult(
            suggested_title=data.get("suggested_title", note.metadata.title),
            suggested_category=category,
            suggested_tags=data.get("suggested_tags", []),
            summary=data.get("summary", ""),
            reasoning=data.get("reasoning", ""),
            action_items=data.get("action_items", []),
        )
