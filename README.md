# AG2: Focus Group Transcript Analyzer

## Overview & Background
This project shows how **AG2 agents** can help market researchers analyze multiple focus group session transcripts and generate a final, unified report. In this example, **two mock focus-group sessions** about a premium concept, **white strawberries**, are analyzed. The transcripts are **synthetic (AI-generated)** and designed to mimic realistic qualitative data.

Quality is driven by an explicit **iterative feedback loop**. For each focus group session, agents draft a report, then cycle through **review → revision → re-review** to catch mistakes, enforce structure, and strengthen evidence. After both session reports are finalized, a second loop **synthesizes** them into a **final unified report**, again with review/revision passes, to ensure the deliverable is clear, accurate, and decision-ready.

**What this illustrates with AG2**
- Automating transcript summarization and **in-depth analysis**  
- Producing **quote-rich, decision-ready** Markdown reports  
- Using **multi-agent, staged iteration** to improve clarity, coverage, and accuracy before anything is marked "final"  

**Key inputs used by the agents**
- Transcripts (mock): `transcripts/fg_1_transcript.txt`, `transcripts/fg_2_transcript.txt`  
- Discussion Guide: `fg_discussion_guide.md`  
- Study Objectives: `fg_objectives.md`  
- Campaign Copy: `marketing_campaign_copy.md`  
- Task Instructions: `individual_fg_report_task_instructions.md`, `final_synthesized_fg_report_task_instructions.md`

---

## Focus Group Objectives
The mock focus groups were designed to explore:

1. **Evaluate Product Concepts & Marketing Copy**  
   Assess five campaign directions for white strawberries (e.g., **Pure Indulgence**, **Snowberry Bliss**, **Nature's White Wonder**, **A Berry Like No Other**, **Sweet Purity**): what resonates, what doesn't, and why.

2. **Identify the Most Promising Concept & Improve It**  
   Capture how participants would refine the leading direction (claims, tone, benefits, language).

3. **Assess Interest and Willingness to Pay (WTP)**  
   Compare **pre- vs. post-exposure interest**, record **favorite concept votes**, and gauge **WTP** relative to red strawberries; surface barriers and how to address them.

Interviews follow a **discussion guide (Q1–Q7)** to reflect common qualitative research structure under realistic time and resource constraints.

---

## Workflow: Iterative Feedback Loop (Quality First)
Both the **per-session analyses** and the **final unified synthesis** use the same staged loop designed to push quality higher with each pass:

**Stages (per session and for the unified report)**
1. **Create** – Draft an initial Markdown report using the transcript(s), discussion guide, objectives, and campaign copy.  
2. **Review** – Check coverage vs. Q1–Q7, accuracy, **quote usage/attribution with timestamps**, consistency with materials, and clarity of quant summaries (pre→post interest, favorite vote, WTP).  
3. **Revise** – Apply feedback; strengthen evidence, structure, and narrative; fix omissions and formatting; re-validate quotes/timestamps.  
4. **Finalize** – Only after quality gates pass (complete Q1–Q7 mapping, concept evaluations, quant summaries, consistent formatting, and the required closing heading).

**Quality gates & checks**
- **Coverage**: Every required section present (Q1–Q7, campaign evaluations, quant summaries)  
- **Evidence**: Multiple **verbatim quotes** per question, attributed with **speaker/segment + HH:MM:SS** timestamps  
- **Consistency**: Campaign names and terminology match the copy; findings align to the guide/objectives  
- **Quant**: Clear roll-ups for **pre→post interest**, **favorite vote**, **WTP** (with rationale)  
- **Formatting**: Clean Markdown and a mandatory final heading **`# End of Report`**

The loop can iterate multiple times (**review ↔ revise**) until the report meets these standards.

---

## Code Walkthrough

This section shows **only** excerpts from the provided code files (`main.py`, `run_indiv_fg_reports.py`, `final_fg_report.py`). Ellipses `...` indicate omitted lines for brevity.

### 1) Entry Point (`main.py`)

```python
from run_indiv_fg_reports import run_indiv_fg_reports
from final_fg_report import run_final_fg_report


num_sessions = 2

def run_project():
    for i in range(1, num_sessions + 1):
        run_indiv_fg_reports(i)
    run_final_fg_report(num_sessions)

if __name__ == "__main__":
    run_project()
```

### 2) Per-Session Feedback Loop (`run_indiv_fg_reports.py`)

**Stages**

```python
class ReportStage(str, Enum):
    CREATE = "create"
    REVIEW = "review"
    REVISE = "revise"
    FINALIZE = "finalize"
```

**Context scaffold (excerpt)**

```python
# Shared context for tracking report state
INITIAL_CONTEXT = {
    # Feedback loop state 
    "loop_started": False,
    "current_iteration": 0,
    "max_iterations": 2,
    "iteration_needed": True,
    ...
}
```

```python
# This resets the context for each run
def make_context() -> ContextVariables:
    # deep-copy so each run is isolated
    return ContextVariables(data=INITIAL_CONTEXT.copy())
```

**Start the loop**

```python
def start_report_creation_process(
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Start the report creation process
    """
    context_variables["loop_started"] = True
    context_variables["current_stage"] = ReportStage.CREATE.value
    context_variables["current_iteration"] = 1

    return ReplyResult(
        message=f"Report creation process started.",
        context_variables=context_variables,
    )
```

**Read inputs**

```python
def read_transcript(context_variables: ContextVariables,
                    session_num: Optional[int] = None) -> str:
    """
    Return the raw transcript text for the current focus group session.
    Falls back to context_variables['session_num'] if no explicit
    session_num argument is provided.
    """
    ...
```

```python
def read_task_instructions(context_variables: ContextVariables) -> str:
    """
    Reads the markdown instructions for the individual focus group report task.
    If the file is missing, stores error context and re-raises the exception.
    """
    file_path = "instructions/individual_fg_report_task_instructions.md"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError as err:
        context_variables["has_error"] = True
        context_variables["error_stage"] = "read_task_instructions"
        context_variables["error_message"] = str(err)
        raise
```

**Create → submit draft**

```python
class ReportDraft(BaseModel):
    title: str = Field(..., description="Report title")
    content: str = Field(..., description="Full text content of the draft")

def submit_report_draft(
    title: Annotated[str, "Report title"],
    content: Annotated[str, "Full text content of the draft"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Submit the report draft for review
    """
    report_draft = ReportDraft(
        title=title,
        content=content
    )
    context_variables["report_draft"] = report_draft.model_dump()
    context_variables["current_stage"] = ReportStage.REVIEW.value

    return ReplyResult(
        message="Report draft submitted. Moving to review stage.",
        context_variables=context_variables,
    )
```

**Review → submit feedback**

```python
class FeedbackItem(BaseModel):
    section: str = Field(..., description="Section of the report the feedback applies to")
    feedback: str = Field(..., description="Detailed feedback")
    severity: str = Field(..., description="Severity level of the feedback: minor, moderate, major, critical")
    recommendation: Optional[str] = Field(..., description="Recommended action to address the feedback")

class FeedbackCollection(BaseModel):
    items: list[FeedbackItem] = Field(..., description="Collection of feedback items")
    overall_assessment: str = Field(..., description="Overall assessment of the report")
    priority_issues: list[str] = Field(..., description="List of priority issues to address")
    iteration_needed: bool = Field(..., description="Whether another iteration is needed")

def submit_feedback(
    items: Annotated[list[FeedbackItem], "Collection of feedback items"],
    overall_assessment: Annotated[str, "Overall assessment of the report"],
    priority_issues: Annotated[list[str], "List of priority issues to address"],
    iteration_needed: Annotated[bool, "Whether another iteration is needed"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Submit feedback on the report
    """
    ...
    context_variables["current_stage"] = ReportStage.REVISE.value

    return ReplyResult(
        message="Feedback submitted. Moving to revision stage.",
        context_variables=context_variables,
    )
```

**Revise → submit revised report (iterate or finalize)**

```python
class RevisedReport(BaseModel):
    title: str = Field(..., description="Report title")
    content: str = Field(..., description="Full text content after revision")
    changes_made: Optional[list[str]] = Field(..., description="List of changes made based on feedback")

def submit_revised_report(
    title: Annotated[str, "Report title"],
    content: Annotated[str, "Full text content after revision"],
    changes_made: Annotated[Optional[list[str]], "List of changes made based on feedback"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Submit the revised report, which may lead to another feedback loop or finalization
    """
    ...
    if context_variables["iteration_needed"] and context_variables["current_iteration"] < context_variables["max_iterations"]:
        context_variables["current_iteration"] += 1
        context_variables["current_stage"] = ReportStage.REVIEW.value
        context_variables["report_draft"] = {
            "title": revised.title,
            "content": revised.content,
        }
        return ReplyResult(
            message=f"Report revised. Starting iteration {context_variables['current_iteration']} with another review.",
            context_variables=context_variables,
        )
    else:
        context_variables["current_stage"] = ReportStage.FINALIZE.value
        return ReplyResult(
            message="Revisions complete. Moving to report finalization.",
            context_variables=context_variables,
        )
```

**Finalize → submit final**

```python
class FinalReport(BaseModel):
    title: str = Field(..., description="Final report title")
    content: str = Field(..., description="Full text content of the final report")

def finalize_report(
    title: Annotated[str, "Final report title"],
    content: Annotated[str, "Full text content of the final report"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Submit the final report and complete the feedback loop
    """
    ...
    context_variables["iteration_needed"] = False

    return ReplyResult(
        message="Report finalized ✅ - terminating workflow",
        context_variables=context_variables,
    )
```

**Agents & pattern (excerpts)**

```python
with llm_config:
    entry_agent = ConversableAgent(
        name="entry_agent",
        system_message="""You are the entry point for the report creation process.
        Your task is to receive report creation requests and start the process.

        Use the start_report_creation_process tool to begin the process.""",
        functions=[start_report_creation_process]
    )

    report_draft_agent = ConversableAgent(
        name="report_draft_agent",
        system_message="""You are the report draft agent for the report creation process.
        Your task is to draft the report and store it in the shared context.""",
        functions=[submit_report_draft, read_transcript, read_task_instructions],
        update_agent_state_before_reply=[UpdateSystemMessage(""" ... """)]
    )

    review_agent = ConversableAgent(
        name="review_agent",
        system_message="You are the report review agent responsible for critical evaluation.",
        functions=[submit_feedback, read_transcript, read_task_instructions],
        update_agent_state_before_reply=[UpdateSystemMessage(""" ... """)]
    )

    revision_agent = ConversableAgent(
        name="revision_agent",
        system_message=""" ... """,
        functions=[submit_revised_report, read_task_instructions]
    )

    finalization_agent = ConversableAgent(
        name="finalization_agent",
        system_message=""" ... """,
        functions=[read_task_instructions, finalize_report]
    )

agent_pattern = DefaultPattern(
    initial_agent=entry_agent,
    agents=[
        entry_agent,
        report_draft_agent,
        review_agent,
        revision_agent,
        finalization_agent
    ],
    context_variables=ctx,
    user_agent=user,
)

chat_result, final_context, last_agent = initiate_group_chat(
    pattern=agent_pattern,
    messages=f"""Write a report that analyzes the results of a transcript for focus group session - {session_num}. 
    The transcript is located in a file called fg_{session_num}_transcript.txt.
    """,
    max_rounds=50, 
)

if final_context.get("final_report"):
    print("Report creation completed successfully!")

    # Write final report to a Markdown file
    os.makedirs("reports", exist_ok=True)
    with open(f"reports/fg_{session_num}_report.md", "w", encoding="utf-8") as f:
        f.write(final_report_content)
```

*Note: The file write uses final_report_content in this excerpt.*

### 3) Unified Synthesis Feedback Loop (`final_fg_report.py`)

**Read per-session reports**

```python
def read_fg_reports(num_sessions: int) -> list[str]:
    """Dynamically read individual focus group reports. The number of focus group reports (sessions) is passed as an argument."""
    reports = []

    for i in range(1, num_sessions + 1):
        report_path = f"reports/fg_{i}_report.md"
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                reports.append(f.read())
        else:
            raise FileNotFoundError(f"Report file not found: {report_path}")

    return reports
```

**Read synthesis instructions (excerpt)**

```python
def read_task_instructions(context_variables: ContextVariables) -> str:
    """
    Reads the markdown instructions for the final synthesized focus group report task.
    If the file is missing, stores error context and re-raises the exception.
    """
    file_path = "instructions/final_synthesized_fg_report_task_instructions.md"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError as err:
        context_variables["has_error"] = True
        context_variables["error_stage"] = "read_task_instructions"
        context_variables["error_message"] = str(err)
        raise
```

**Finalize unified report (excerpt)**

```python
def finalize_report(
    title: Annotated[str, "Final report title"],
    content: Annotated[str, "Full text content of the final report"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Submit the final report and complete the feedback loop
    """
    final = FinalReport(
        title=title,
        content=content,
    )
    context_variables["final_report"] = final.model_dump()
    context_variables["iteration_needed"] = False

    return ReplyResult(
        message="Report finalized ✅ – terminating workflow.",
        target=TerminateTarget(),  
        context_variables=context_variables,
    )
```

**Run synthesis + write file (excerpt)**

```python
def run_final_fg_report(num_sessions: int): 
    """Run the feedback loop pattern for report creation with iterative refinement"""
    print("Initiating Feedback Loop Pattern for Report Creation...")

    agent_pattern = DefaultPattern(
        initial_agent=entry_agent,
        agents=[
            entry_agent,
            report_draft_agent,
            review_agent,
            revision_agent,
            finalization_agent
        ],
        context_variables=ctx,
        user_agent=user,
    )

    chat_result, final_context, last_agent = initiate_group_chat(
        pattern=agent_pattern,
        messages="Write a final report that synthesizes the results of multiple focus group session reports.",
        max_rounds=50, 
    )

    if final_context.get("final_report"):
        print("Report creation completed successfully!")
       
        # Write final report to a Markdown file
        os.makedirs("reports", exist_ok=True)
        with open("reports/final_unified_fg_report.md", "w", encoding="utf-8") as f:
            f.write(final_report_content)
```

---

## Output Showcase

### Per-Session Reports (Generated)
- `reports/fg_1_report.md`
- `reports/fg_2_report.md`

Each contains: executive summary; participant profile; Q1–Q7 analyses with multiple quotes and timestamps; concept-by-concept evaluations of the five campaigns; pre→post interest and favorite vote summaries; WTP vs. red strawberries; implications; and the final heading `# End of Report`.

### Final Unified Report (Generated)
- `reports/final_unified_fg_report.md`

This synthesis compares/contrasts insights across the two sessions and age segments, aggregates campaign performance, rolls up quant signals (pre→post interest, favorite vote, WTP), and presents prioritized implications and recommendations, ending with `# End of Report`.

---

## Conclusion
This project pairs multi-agent specialization with explicit iterative feedback loops to transform two lengthy, synthetic focus-group transcripts into three decision-ready artifacts (two per-session reports + one unified synthesis). The repeated review → revision passes are the core of the approach—systematically elevating clarity, coverage, and accuracy before anything is marked "final."
