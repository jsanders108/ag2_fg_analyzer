# ---------------------------------------------------------------------
# Orchestration Entrypoint for Focus Group Reporting (AG2)
# ---------------------------------------------------------------------
# This script coordinates the full workflow:
#   1) Generates individual focus group (FG) reports for each session.
#   2) Builds a final synthesized report that aggregates all session reports.
#
# Pipeline Overview
# -----------------
# • run_indiv_fg_reports(session_num)
#     - Reads transcript + instructions for a single session.
#     - Runs a multi-agent feedback loop (create → review → revise → finalize).
#     - Outputs: reports/fg_{session_num}_report.md
#
# • run_final_fg_report(num_sessions)
#     - Reads all individual session reports produced above.
#     - Runs a multi-agent feedback loop to synthesize a unified final report.
#     - Outputs: reports/final_unified_fg_report.md
#
# Usage
# -----
# • Set num_sessions below to the number of sessions you want to process.
# • Ensure required inputs exist before running:
#     - transcripts/fg_{n}_transcript.txt (used by the individual report pipeline)
#     - instructions/individual_fg_report_task_instructions.md
#     - instructions/final_synthesized_fg_report_task_instructions.md
# • Run: `python orchestrate_project.py` (or whatever filename you save this as)
#
# Notes
# -----
# • This file intentionally keeps orchestration minimal and explicit.
# • Order matters: all per-session reports are created before synthesis runs.
# • Errors from deeper pipelines will surface via their own logging/prints.
# ---------------------------------------------------------------------

from run_indiv_fg_reports import run_indiv_fg_reports
from final_fg_report import run_final_fg_report

# Number of focus group sessions to process end-to-end.
# Update this to match the number of available transcripts/reports.
num_sessions = 2

def run_project():
    """
    Orchestrate the full reporting workflow:
      1) Loop over sessions to produce individual reports.
      2) Produce the final synthesized report from those outputs.
    """
    for i in range(1, num_sessions + 1):
        run_indiv_fg_reports(i)
    run_final_fg_report(num_sessions)

if __name__ == "__main__":
    # Entry point for CLI execution. Keeps imports side-effect-free.
    run_project()
