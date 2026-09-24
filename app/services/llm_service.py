import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings


@dataclass(frozen=True)
class QueryPlan:
    """Small, validated contract between the LLM and deterministic analytics."""

    intent: str
    priority: str | None = None
    category: str | None = None
    status: str | None = None
    time_window: str | None = None
    unresolved_within_hrs: float | None = None


class LLMService:
    """Structured intent planning and grounded answer phrasing through an LLM."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def model_label(self) -> str:
        if self.settings.llm_provider == "none":
            return "deterministic-fallback"
        return f"{self.settings.llm_provider}:{self.settings.llm_model}"

    def answer(self, question: str, result: dict[str, Any]) -> str:
        fallback = result["answer_seed"]
        if self.settings.llm_provider == "none":
            return fallback

        prompt = self._prompt(question, result)
        try:
            if self.settings.llm_provider == "ollama":
                return self._ollama(prompt) or fallback
            return self._openai_compatible(prompt) or fallback
        except (httpx.HTTPError, OSError, ValueError, KeyError):
            return fallback

    def interpret(self, question: str) -> QueryPlan | None:
        """Ask the configured model for a JSON query plan.

        A malformed response is treated as an unavailable model. The analytics
        layer then uses its deterministic parser, so an LLM outage cannot
        produce ungrounded numbers or take the API down.
        """

        if self.settings.llm_provider == "none":
            return None
        prompt = (
            "Classify the support-ticket question into a JSON object. Return JSON only, "
            "with exactly these keys: intent, priority, category, status, time_window, "
            "unresolved_within_hrs. intent must be one of count, average_rating, "
            "agent_ranking, ticket_search, anomaly_summary. Use null for unknown fields. "
            "priority is Low, Medium, High, or Critical; category is Billing, Technical, "
            "or General; status is Open, Resolved, Escalated, or unresolved; "
            "time_window is week or month. For questions about tickets not resolved "
            "within N hours, set unresolved_within_hrs to N. Do not answer the question.\n\n"
            f"Question: {question}"
        )
        try:
            raw = self._ollama(prompt, json_mode=True) if self.settings.llm_provider == "ollama" else self._openai_compatible(prompt)
            if "```" in raw:
                raw = raw.replace("```json", "").replace("```", "").strip()
            payload = json.loads(raw)
            return self._validated_plan(payload)
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    @staticmethod
    def _validated_plan(payload: Any) -> QueryPlan:
        if not isinstance(payload, dict):
            raise ValueError("LLM plan must be a JSON object")
        allowed_intents = {"count", "average_rating", "agent_ranking", "ticket_search", "anomaly_summary"}
        allowed_priorities = {"Low", "Medium", "High", "Critical"}
        allowed_categories = {"Billing", "Technical", "General"}
        allowed_statuses = {"Open", "Resolved", "Escalated", "unresolved"}
        allowed_windows = {"week", "month"}
        intent = payload.get("intent")
        if intent not in allowed_intents:
            raise ValueError("Unsupported LLM intent")

        def optional(value: Any, allowed: set[str]) -> str | None:
            if value is None:
                return None
            if value not in allowed:
                raise ValueError(f"Invalid LLM filter value: {value}")
            return value

        threshold = payload.get("unresolved_within_hrs")
        if threshold is not None:
            threshold = float(threshold)
            if not 0 < threshold <= 720:
                raise ValueError("Invalid unresolved threshold")
        return QueryPlan(
            intent=intent,
            priority=optional(payload.get("priority"), allowed_priorities),
            category=optional(payload.get("category"), allowed_categories),
            status=optional(payload.get("status"), allowed_statuses),
            time_window=optional(payload.get("time_window"), allowed_windows),
            unresolved_within_hrs=threshold,
        )

    def _prompt(self, question: str, result: dict[str, Any]) -> str:
        context = {
            "intent": result["intent"],
            "answer_seed": result["answer_seed"],
            "computed_data": result.get("data", []),
            "evidence": result.get("evidence", []),
        }
        return (
            "You answer support operations questions using only the supplied computed context. "
            "Do not invent values, tickets, dates, or causes. Keep the answer concise and mention "
            "the relevant count or metric first. If evidence is present, refer to ticket IDs. "
            "Return plain text, not JSON or markdown tables.\n\n"
            f"Question: {question}\n"
            f"Computed context: {json.dumps(context, default=str)}"
        )

    def _ollama(self, prompt: str, json_mode: bool = False) -> str:
        url = f"{self.settings.llm_base_url.rstrip('/')}/api/generate"
        request = {"model": self.settings.llm_model, "prompt": prompt, "stream": False}
        if json_mode:
            request["format"] = "json"
        response = httpx.post(
            url,
            json=request,
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        return str(response.json().get("response", "")).strip()

    def _openai_compatible(self, prompt: str) -> str:
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self.settings.openai_api_key or ''}"},
            json={
                "model": self.settings.llm_model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": "You are a precise support analytics assistant."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"]).strip()
