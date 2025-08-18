# =============================================================================
# Orchestration Entrypoint for Focus Group Reporting (AG2)
# ---------------------------------------------------------------------
# This script coordinates the full workflow:
#   1) Generates individual focus group (FG) reports for each session.
#   2) Builds a final synthesized report that aggregates all session reports.
# =============================================================================

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
    run_project()


