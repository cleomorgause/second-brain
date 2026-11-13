"""Configuração global de fixtures e ambiente de testes para o pytest."""

import os

# Desativa chamadas de rede externas e telemetria do LiteLLM durante a execução dos testes
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
