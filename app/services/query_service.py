import re
from collections import Counter, defaultdict
from datetime import timedelta
from statistics import mean
from typing import Any

from app.config import Settings, get_settings
from app.services.anomaly_service import AnomalyService
from app.services.llm_service import LLMService, QueryPlan


class QueryService:
    """Parse common support analytics questions and ground answers in CSV rows."""

    STOP_WORDS = {
        "a", "an", "and", "are", "be", "by", "for", "from", "how", "in", "is", "me",
        "of", "on", "or", "show", "the", "there", "this", "to", "what", "which", "within",
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.llm = LLMService(self.settings)
        self.anomalies = AnomalyService()

    def run(self, question: str, rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
        normalized = question.lower().strip()
        plan = self.llm.interpret(question)
        intent = plan.intent if plan else None
        if intent == "anomaly_summary" or (intent is None and "anomal" in normalized):
            anomaly_rows = self._filter_rows(rows, normalized, plan)
            anomaly_result = self.anomalies.detect(anomaly_rows or rows)
            seed = (
                f"Found {anomaly_result['summary']['total']} anomalies: "
                f"{anomaly_result['summary']['critical']} critical, "
                f"{anomaly_result['summary']['high']} high, and "
                f"{anomaly_result['summary']['medium']} medium."
            )
            return self._finish(question, "anomaly_summary", seed, anomaly_result["anomalies"], anomaly_result["summary"])

        filtered = self._filter_rows(rows, normalized, plan)
        if intent == "average_rating" or (intent is None and self._asks_average_rating(normalized)):
            return self._rating_result(question, normalized, filtered)
        if intent == "agent_ranking" or (intent is None and self._asks_agent_ranking(normalized)):
            return self._agent_ranking_result(question, filtered)
        if intent == "count" or (intent is None and self._asks_count(normalized)):
            seed = f"There are {len(filtered)} matching tickets."
            return self._finish(question, "count", seed, filtered[: self.settings.max_evidence_items], [{"count": len(filtered)}])

        ranked = self._rank_rows(question, filtered or list(rows))
        shown = ranked[: self.settings.max_evidence_items]
        if intent == "ticket_search" or self._asks_list(normalized) or filtered:
            seed = f"Found {len(filtered)} matching tickets. Showing {len(shown)} as evidence."
            return self._finish(question, "ticket_search", seed, shown, [self._public_ticket(row) for row in shown])

        seed = f"I found {len(shown)} relevant tickets in the dataset."
        return self._finish(question, "ticket_search", seed, shown, [self._public_ticket(row) for row in shown])

    def _finish(
        self,
        question: str,
        intent: str,
        answer_seed: str,
        evidence: list[dict[str, Any]] | list[Any],
        data: list[dict[str, Any]] | dict[str, Any],
    ) -> dict[str, Any]:
        evidence_rows = [item["ticket"] if "ticket" in item else item for item in evidence]
        public_evidence = [self._public_ticket(row) for row in evidence_rows]
        result = {"intent": intent, "answer_seed": answer_seed, "data": data, "evidence": public_evidence}
        return {
            "question": question,
            "answer": self.llm.answer(question, result),
            "intent": intent,
            "model": self.llm.model_label,
            "data": data if isinstance(data, list) else [data],
            "evidence": public_evidence,
        }

    def _filter_rows(
        self,
        rows: tuple[dict[str, Any], ...],
        question: str,
        plan: QueryPlan | None = None,
    ) -> list[dict[str, Any]]:
        filtered = list(rows)
        priority_filter = plan.priority.lower() if plan and plan.priority else None
        for priority in ("critical", "high", "medium", "low"):
            if priority_filter == priority or (priority_filter is None and priority in question):
                filtered = [row for row in filtered if row["priority"].lower() == priority]
                break

        category_filter = plan.category.lower() if plan and plan.category else None
        for category in ("billing", "technical", "general"):
            if category_filter == category or (category_filter is None and category in question):
                filtered = [row for row in filtered if row["category"].lower() == category]
                break

        threshold = plan.unresolved_within_hrs if plan else None
        if threshold is not None or "not resolved within" in question or "not resolved in" in question:
            threshold = threshold or self._hours_from_question(question, 12.0)
            filtered = [
                row for row in filtered
                if row["status"] != "Resolved"
                or row["resolution_time_hrs"] is None
                or row["resolution_time_hrs"] > threshold
            ]
        elif plan and plan.status:
            if plan.status == "unresolved":
                filtered = [row for row in filtered if row["status"] != "Resolved"]
            else:
                filtered = [row for row in filtered if row["status"] == plan.status]
        elif "currently open" in question or "open tickets" in question:
            filtered = [row for row in filtered if row["status"] == "Open"]
        elif "unresolved" in question or "open" in question:
            filtered = [row for row in filtered if row["status"] != "Resolved"]
        elif "resolved" in question:
            filtered = [row for row in filtered if row["status"] == "Resolved"]
        elif "escalated" in question:
            filtered = [row for row in filtered if row["status"] == "Escalated"]

        time_window = plan.time_window if plan else None
        if time_window or "this month" in question or "this week" in question:
            latest = max(row["created_at"] for row in rows)
            start = latest.replace(day=1, hour=0, minute=0) if time_window == "month" or "this month" in question else latest - timedelta(days=7)
            filtered = [row for row in filtered if row["created_at"] >= start]
        return filtered

    @staticmethod
    def _hours_from_question(question: str, default: float) -> float:
        match = re.search(r"(\d+(?:\.\d+)?)\s*hours?", question)
        return float(match.group(1)) if match else default

    @staticmethod
    def _asks_count(question: str) -> bool:
        return any(phrase in question for phrase in ("how many", "number of", "count", "currently open"))

    @staticmethod
    def _asks_list(question: str) -> bool:
        return any(phrase in question for phrase in ("show", "list", "which tickets", "all ", "find"))

    @staticmethod
    def _asks_average_rating(question: str) -> bool:
        return "average" in question and "rating" in question

    @staticmethod
    def _asks_agent_ranking(question: str) -> bool:
        return "agent" in question and any(word in question for word in ("most", "lowest", "highest", "best", "worst"))

    def _rating_result(self, question: str, normalized: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        rated = [row for row in rows if row["customer_rating"] is not None]
        group_key = "category" if "category" in normalized else "agent_id" if "agent" in normalized else None
        is_ranking = any(word in normalized for word in ("lowest", "highest", "best", "worst", "by category", "by agent"))
        if group_key and is_ranking:
            grouped: dict[str, list[int]] = defaultdict(list)
            for row in rated:
                grouped[row[group_key]].append(row["customer_rating"])
            metrics = [
                {"group": key, "average_rating": round(mean(values), 2), "rated_tickets": len(values)}
                for key, values in grouped.items()
            ]
            metrics.sort(key=lambda item: item["average_rating"], reverse="highest" in normalized or "best" in normalized)
            lead = metrics[0] if metrics else None
            seed = (
                f"{lead['group']} has the {'highest' if 'highest' in normalized or 'best' in normalized else 'lowest'} "
                f"average customer rating at {lead['average_rating']:.2f} across {lead['rated_tickets']} rated tickets."
                if lead else "No rated tickets matched the filters."
            )
            return self._finish(question, "average_rating_by_group", seed, rows[: self.settings.max_evidence_items], metrics)
        average = round(mean(row["customer_rating"] for row in rated), 2) if rated else None
        label = next((row["category"] for row in rows), "the matching tickets") if group_key == "category" else "the matching tickets"
        seed = (
            f"The average customer rating for {label} is {average:.2f} across {len(rated)} rated tickets."
            if average is not None
            else "No rated tickets matched the filters."
        )
        return self._finish(question, "average_rating", seed, rows[: self.settings.max_evidence_items], [{"average_rating": average, "rated_tickets": len(rated)}])

    def _agent_ranking_result(self, question: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        resolved = [row for row in rows if row["status"] == "Resolved"]
        counts = Counter(row["agent_id"] for row in resolved)
        ranking = [{"agent_id": agent, "resolved_tickets": count} for agent, count in counts.most_common()]
        if "lowest" in question or "worst" in question:
            ranking.sort(key=lambda item: (item["resolved_tickets"], item["agent_id"]))
        lead = ranking[0] if ranking else None
        seed = f"{lead['agent_id']} resolved the most tickets with {lead['resolved_tickets']}." if lead else "No resolved tickets matched the filters."
        return self._finish(question, "agent_ranking", seed, rows[: self.settings.max_evidence_items], ranking)

    def _rank_rows(self, question: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        terms = set(re.findall(r"[a-z0-9]+", question.lower())) - self.STOP_WORDS
        scored = []
        for row in rows:
            haystack = " ".join(str(row[field]).lower() for field in ("issue_summary", "category", "priority", "status", "agent_id"))
            score = sum(term in haystack for term in terms)
            if "long" in question or "resolution" in question:
                score += (row["resolution_time_hrs"] or 0) / 100
            scored.append((score, row["created_at"], row))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored]

    @staticmethod
    def _public_ticket(row: dict[str, Any]) -> dict[str, Any]:
        public = dict(row)
        if hasattr(row["created_at"], "isoformat"):
            public["created_at"] = row["created_at"].isoformat(timespec="minutes")
        return public
