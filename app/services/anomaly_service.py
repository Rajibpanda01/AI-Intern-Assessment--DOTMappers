from datetime import datetime
from statistics import mean
from typing import Any


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _ticket_public(row: dict[str, Any]) -> dict[str, Any]:
    ticket = dict(row)
    ticket["created_at"] = row["created_at"].isoformat(timespec="minutes")
    return ticket


class AnomalyService:
    def detect(
        self,
        rows: tuple[dict[str, Any], ...] | list[dict[str, Any]],
        hours_threshold: float = 24.0,
        limit: int = 50,
    ) -> dict[str, Any]:
        if not rows:
            raise ValueError("Cannot detect anomalies in an empty dataset")

        reference_time = max(row["created_at"] for row in rows)
        resolution_values = [
            row["resolution_time_hrs"] for row in rows if row["resolution_time_hrs"] is not None
        ]
        response_values = [
            row["response_time_hrs"] for row in rows if row["response_time_hrs"] is not None
        ]
        resolution_q1 = _quantile(resolution_values, 0.25)
        resolution_q3 = _quantile(resolution_values, 0.75)
        response_q1 = _quantile(response_values, 0.25)
        response_q3 = _quantile(response_values, 0.75)
        resolution_threshold = max(24.0, resolution_q3 + 1.5 * (resolution_q3 - resolution_q1))
        response_threshold = response_q3 + 1.5 * (response_q3 - response_q1)

        anomalies: list[dict[str, Any]] = []
        for row in rows:
            resolution = row["resolution_time_hrs"]
            if resolution is not None and resolution > resolution_threshold:
                severity = "critical" if resolution > resolution_threshold * 1.5 else "high"
                anomalies.append(
                    {
                        "anomaly_type": "long_resolution",
                        "severity": severity,
                        "reason": (
                            f"Resolution time {resolution:.1f}h exceeds the statistical threshold "
                            f"of {resolution_threshold:.1f}h."
                        ),
                        "ticket": _ticket_public(row),
                    }
                )

            age_hours = (reference_time - row["created_at"]).total_seconds() / 3600
            if row["status"] != "Resolved" and row["priority"] in {"Critical", "High"} and age_hours > hours_threshold:
                severity = "critical" if row["priority"] == "Critical" else "high"
                anomalies.append(
                    {
                        "anomaly_type": "stale_unresolved",
                        "severity": severity,
                        "reason": (
                            f"{row['priority']} ticket is {age_hours:.1f}h old and remains "
                            f"{row['status'].lower()}."
                        ),
                        "ticket": _ticket_public(row),
                    }
                )

            response = row["response_time_hrs"]
            if response is not None and response > response_threshold:
                anomalies.append(
                    {
                        "anomaly_type": "response_time_spike",
                        "severity": "medium",
                        "reason": (
                            f"First response time {response:.1f}h exceeds the statistical threshold "
                            f"of {response_threshold:.1f}h."
                        ),
                        "ticket": _ticket_public(row),
                    }
                )

        severity_order = {"critical": 0, "high": 1, "medium": 2}
        anomalies.sort(key=lambda item: (severity_order[item["severity"]], item["ticket"]["ticket_id"]))
        anomalies = anomalies[:limit]
        summary = {
            "total": len(anomalies),
            "critical": sum(item["severity"] == "critical" for item in anomalies),
            "high": sum(item["severity"] == "high" for item in anomalies),
            "medium": sum(item["severity"] == "medium" for item in anomalies),
        }
        return {
            "reference_time": reference_time,
            "thresholds": {
                "hours_threshold": hours_threshold,
                "long_resolution_hrs": round(resolution_threshold, 2),
                "response_time_hrs": round(response_threshold, 2),
            },
            "summary": summary,
            "anomalies": anomalies,
        }
