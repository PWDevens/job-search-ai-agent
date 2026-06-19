"""
Metrics collection and reporting for persona evaluation tests.
Captures all search results and evaluation metrics to CSV for analysis.
"""
import csv
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class SearchMetrics:
    """Metrics captured for a single search"""
    timestamp: str
    persona: str
    search_variant: str
    search_query: str
    geo_preference: Optional[str]
    used_resume: bool
    execution_time_sec: float
    jobs_returned: int
    jobs_score_avg: float
    recommendations_returned: int
    blind_spots_returned: int
    validation_resume_coach: bool
    validation_career_strategist: bool
    fallback_used: bool
    error_message: Optional[str]
    raw_agent_output_length: int


class MetricsCollector:
    """Collects and exports search metrics"""

    def __init__(self, output_dir: Path = None):
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "reports"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.metrics: List[SearchMetrics] = []

    def record_search(
        self,
        persona: str,
        search_variant: str,
        search_query: str,
        geo_preference: Optional[str],
        used_resume: bool,
        execution_time_sec: float,
        result: Dict[str, Any],
        error_message: Optional[str] = None,
    ) -> None:
        """Record metrics for a completed search"""

        top_jobs = result.get("top_jobs", [])
        resume_recs = result.get("resume_recs", [])
        blind_spots = result.get("blind_spots", [])
        agent_validation = result.get("agent_validation", {})
        raw_agent_output = result.get("raw_agent_output", {})

        # Calculate job score average
        jobs_score_avg = (
            sum(j.get("score", 0) for j in top_jobs) / len(top_jobs)
            if top_jobs
            else 0
        )

        # Check if fallback was used
        fallback_used = any(
            not v for v in agent_validation.values()
        )

        # Raw output size
        raw_output_str = json.dumps(raw_agent_output) if raw_agent_output else ""
        raw_output_length = len(raw_output_str)

        metrics = SearchMetrics(
            timestamp=datetime.now().isoformat(),
            persona=persona,
            search_variant=search_variant,
            search_query=search_query,
            geo_preference=geo_preference,
            used_resume=used_resume,
            execution_time_sec=execution_time_sec,
            jobs_returned=len(top_jobs),
            jobs_score_avg=jobs_score_avg,
            recommendations_returned=len(resume_recs),
            blind_spots_returned=len(blind_spots),
            validation_resume_coach=agent_validation.get("resume_coach", False),
            validation_career_strategist=agent_validation.get("career_strategist", False),
            fallback_used=fallback_used,
            error_message=error_message,
            raw_agent_output_length=raw_output_length,
        )

        self.metrics.append(metrics)

    def export_csv(self, filename: str = "persona_results.csv") -> Path:
        """Export metrics to CSV file"""
        output_path = self.output_dir / filename

        if not self.metrics:
            print(f"No metrics to export")
            return output_path

        with open(output_path, "w", newline="") as f:
            fieldnames = [field.name for field in self.metrics[0].__dataclass_fields__.values()]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for metric in self.metrics:
                writer.writerow(asdict(metric))

        print(f"Exported {len(self.metrics)} search metrics to {output_path}")
        return output_path

    def generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics"""
        if not self.metrics:
            return {"total_searches": 0}

        total_searches = len(self.metrics)
        successful_searches = sum(1 for m in self.metrics if m.error_message is None)
        failed_searches = total_searches - successful_searches
        avg_execution_time = sum(m.execution_time_sec for m in self.metrics) / total_searches
        avg_jobs_returned = sum(m.jobs_returned for m in self.metrics) / total_searches
        avg_recs_returned = sum(m.recommendations_returned for m in self.metrics) / total_searches
        avg_spots_returned = sum(m.blind_spots_returned for m in self.metrics) / total_searches
        fallback_count = sum(1 for m in self.metrics if m.fallback_used)
        fallback_rate = (fallback_count / total_searches * 100) if total_searches > 0 else 0

        return {
            "total_searches": total_searches,
            "successful_searches": successful_searches,
            "failed_searches": failed_searches,
            "success_rate_percent": (successful_searches / total_searches * 100) if total_searches > 0 else 0,
            "avg_execution_time_sec": avg_execution_time,
            "avg_jobs_returned": avg_jobs_returned,
            "avg_recommendations_returned": avg_recs_returned,
            "avg_blind_spots_returned": avg_spots_returned,
            "fallback_usage_count": fallback_count,
            "fallback_usage_percent": fallback_rate,
        }

    def print_summary(self) -> None:
        """Print summary statistics"""
        summary = self.generate_summary()
        print("\n" + "=" * 60)
        print("PHASE 2 INITIAL TESTING — SUMMARY")
        print("=" * 60)
        print(f"Total Searches: {summary.get('total_searches', 0)}")
        print(f"Successful: {summary.get('successful_searches', 0)}")
        print(f"Failed: {summary.get('failed_searches', 0)}")
        print(f"Success Rate: {summary.get('success_rate_percent', 0):.1f}%")
        print(f"\nExecution Time (avg): {summary.get('avg_execution_time_sec', 0):.2f}s")
        print(f"Jobs Returned (avg): {summary.get('avg_jobs_returned', 0):.1f}")
        print(f"Recommendations (avg): {summary.get('avg_recommendations_returned', 0):.1f}")
        print(f"Blind Spots (avg): {summary.get('avg_blind_spots_returned', 0):.1f}")
        print(f"\nFallback Usage: {summary.get('fallback_usage_count', 0)} ({summary.get('fallback_usage_percent', 0):.1f}%)")
        print("=" * 60 + "\n")
