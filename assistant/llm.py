import json
import urllib.request
from langchain_openai import ChatOpenAI
from .config import LLM_BASE_URL, LLM_MODEL

_cache = {}


def _model_name() -> str:
    if LLM_MODEL:
        return LLM_MODEL
    with urllib.request.urlopen(LLM_BASE_URL + "/models", timeout=10) as r:
        return json.load(r)["data"][0]["id"]


def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """LLM local servi par vLLM (API compatible OpenAI), via LangChain."""
    if temperature not in _cache:
        _cache[temperature] = ChatOpenAI(
            model=_model_name(), base_url=LLM_BASE_URL, api_key="EMPTY", temperature=temperature,
            max_tokens=500, timeout=120,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    return _cache[temperature]
