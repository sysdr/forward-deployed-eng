"""Turns a measured baseline into a scoping pack.

Nothing here is clever. The value is that every number in the output traces to
a measurement rather than to a meeting, and that the kill criteria are written
down before anyone is emotionally invested in the project.
"""
from __future__ import annotations

from src.models import BaselineReport, ScopingPack, SuccessCriterion

TARGET_ACCURACY_AT_5 = 0.90
TARGET_P50_SECONDS = 60.0


def build_scoping_pack(report: BaselineReport) -> ScopingPack:
    """Derive the week-one deliverable from the measured baseline."""
    return ScopingPack(
        customer="Meridian Mutual",
        stated_ask="Use AI to speed up claims.",
        restated_problem=(
            "Adjusters answering a question about an existing claim reach the "
            f"answering document within the first five results {report.accuracy_at_5:.0%} "
            "of the time. On questions phrased in a claimant's words rather than with "
            f"a claim number, that falls to {report.accuracy_concept:.0%}. "
            f"Median time to answer is {report.p50_minutes} minutes and the mean is "
            f"{report.mean_minutes} minutes, because a failed search costs a manual "
            "folder review."
        ),
        success_criteria=[
            SuccessCriterion(
                name="Answer found in top 5",
                baseline=f"{report.accuracy_at_5:.0%}",
                target=f"{TARGET_ACCURACY_AT_5:.0%}",
                measured_by="The 40-question set in tests/, rerun on every change.",
            ),
            SuccessCriterion(
                name="Answer found for questions without a claim number",
                baseline=f"{report.accuracy_concept:.0%}",
                target=f"{TARGET_ACCURACY_AT_5:.0%}",
                measured_by="The concept subset of the same question set.",
            ),
            SuccessCriterion(
                name="Median time to answer",
                baseline=f"{report.p50_minutes} min",
                target=f"under {TARGET_P50_SECONDS / 60:.0f} min",
                measured_by=(
                    f"Rank of the answering document x {report.seconds_per_document:.0f}s "
                    "per document read."
                ),
            ),
            SuccessCriterion(
                name="Questions falling back to manual review",
                baseline=f"{report.fallback_rate:.0%}",
                target="under 10%",
                measured_by="Share of questions where no result contained the answer.",
            ),
        ],
        kill_criteria=[
            "Concept-question accuracy does not exceed 75% after two weeks of work.",
            "Median time to answer does not improve by at least half.",
            "Cost per answered question exceeds the adjuster minutes it saves.",
            "The corpus cannot be indexed without moving claim data off Meridian's network.",
        ],
        out_of_scope=[
            "Automating the coverage decision itself.",
            "Writing to the claims system of record.",
            "Any claim document containing medical records, until lesson 31.",
        ],
    )


def render(pack: ScopingPack, report: BaselineReport) -> str:
    """Render the pack as the markdown you would actually send the customer."""
    lines = [
        f"# Scoping Pack — {pack.customer}",
        "",
        f"**Stated ask:** {pack.stated_ask}",
        "",
        "## Restated as something measurable",
        "",
        pack.restated_problem,
        "",
        f"Measured over {report.questions_asked} questions against "
        f"{report.corpus_documents} documents.",
        "",
        "## Success criteria",
        "",
        "| Criterion | Today | Target | Measured by |",
        "|---|---|---|---|",
    ]
    for c in pack.success_criteria:
        lines.append(f"| {c.name} | {c.baseline} | {c.target} | {c.measured_by} |")
    lines += ["", "## Kill criteria", "", "We stop if any of these holds.", ""]
    lines += [f"{i}. {k}" for i, k in enumerate(pack.kill_criteria, 1)]
    lines += ["", "## Out of scope", ""]
    lines += [f"- {o}" for o in pack.out_of_scope]
    lines.append("")
    return "\n".join(lines)
