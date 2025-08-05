from run_indiv_fg_reports import run_indiv_fg_reports
from final_fg_report import run_final_fg_report


num_sessions = 2

def run_project():
    for i in range(1, num_sessions + 1):
        run_indiv_fg_reports(i)
    run_final_fg_report(num_sessions)

if __name__ == "__main__":
    run_project() 