# ---------------------------------------------------------------------
# Feedback Loop Pattern for Iterative Document Refinement (AG2)
# ---------------------------------------------------------------------
# This script synthesizes a *final* focus group report by orchestrating
# multiple AG2 agents in a structured feedback loop:
#
#   1) entry_agent          → Starts the workflow.
#   2) report_draft_agent   → Drafts the synthesized final report (from existing per-session reports).
#   3) review_agent         → Critically evaluates the draft and submits structured feedback.
#   4) revision_agent       → Applies feedback; either loops for another review or proceeds to finalize.
#   5) finalization_agent   → Polishes and finalizes the report, then terminates the workflow.
#
# Key Ideas:
#   • ContextVariables store loop state (stage, iteration count) and artifacts (draft, feedback, revised, final).
#   • OnContextCondition routes control between agents based on shared context flags.
#   • Pydantic models (ReportDraft, FeedbackCollection, RevisedReport, FinalReport) enforce typed payloads.
#
# Expected Files & Folders:
#   • Input:  reports/fg_1_report.md, reports/fg_2_report.md, ... (individual session reports)
#   • Input:  instructions/final_synthesized_fg_report_task_instructions.md
#   • Output: reports/final_unified_fg_report.md
#
# Note: System messages mention tools "read_session_reports" in some places;
# the actual function is read_fg_reports(). This is intentional to preserve your code.
# ---------------------------------------------------------------------

from typing import Annotated, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field
from autogen import (
    ConversableAgent,
    UserProxyAgent,
    ContextExpression,
    LLMConfig,
    UpdateSystemMessage,
)
from autogen.agentchat import initiate_group_chat
from autogen.agentchat.group import AgentTarget, ContextVariables, ReplyResult, TerminateTarget, OnContextCondition, ExpressionContextCondition, RevertToUserTarget
from autogen.agentchat.group.patterns import DefaultPattern

from dotenv import load_dotenv
import os

# Load environment variables (e.g., OPENAI_API_KEY)
load_dotenv()

# ---------------------------------------------------------------------
# LLM Configuration (shared across all agents)
# ---------------------------------------------------------------------
# "tool_choice" = "required" enforces tool-calling behavior—critical for
# ensuring each stage submits via the correct function.
llm_config = LLMConfig(
    api_type="openai",
    #model="gpt-4.1",
    model="gpt-4.1-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0,           # Deterministic outputs aid repeatability
    cache_seed=None,
    parallel_tool_calls=False,
    tool_choice="required"
)

# Feedback severity taxonomy (used in comments/instructions):
#   minor, moderate, major, critical

# ---------------------------------------------------------------------
# Workflow Stage Tracking
# ---------------------------------------------------------------------
# Drives OnContextCondition routing between agents via shared context.
class ReportStage(str, Enum):
    CREATE = "create"
    REVIEW = "review"
    REVISE = "revise"
    FINALIZE = "finalize" 

# ---------------------------------------------------------------------
# Shared Context (single run)
# ---------------------------------------------------------------------
# This ContextVariables holds *all* state and artifacts for the run.
# Agents mutate this object to pass work along the pipeline.
shared_context = ContextVariables(data={
    # Feedback loop state 
    "loop_started": False,
    "current_iteration": 0,
    "max_iterations": 2,       # Guardrail to avoid infinite loops
    "iteration_needed": True,
    "current_stage": ReportStage.CREATE,
 
    # Report data at various stages
    "report_draft": {},
    "feedback_collection": {},
    "revised_report": {},
    "final_report": {},

    # Error state (helps surface missing files, etc.)
    "has_error": False,
    "error_message": "",
    "error_stage": ""
}) 

# ---------------------------------------------------------------------
# Stage-Transition & I/O Functions (tool-called by agents)
# ---------------------------------------------------------------------

def start_report_creation_process(
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Initialize the loop, set stage to CREATE, and bump iteration to 1.
    This is called by entry_agent to kick off the pipeline.
    """
    context_variables["loop_started"] = True  # Drives OnContextCondition to the next agent
    context_variables["current_stage"] = ReportStage.CREATE.value  # Drives OnContextCondition to the next agent
    context_variables["current_iteration"] = 1

    return ReplyResult(
        message=f"Report creation process started.",
        context_variables=context_variables,
    )

def read_fg_reports(num_sessions: int) -> list[str]:
    """
    Load the *individual* focus group reports that will be synthesized.
    - Expected paths: reports/fg_{i}_report.md for i in [1..num_sessions]
    - Raises FileNotFoundError if any expected report is missing.
    """
    reports = []

    for i in range(1, num_sessions + 1):
        report_path = f"reports/fg_{i}_report.md"
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                reports.append(f.read())
        else:
            # Fail fast so the calling agent can surface the issue
            raise FileNotFoundError(f"Report file not found: {report_path}")

    return reports

def read_task_instructions(context_variables: ContextVariables) -> str:
    """
    Load the Markdown instructions for the *final synthesized* report task.
    If missing, record error info in context and re-raise the exception.
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

# ---------------------------------------------------------------------
# Data Models & Submission Functions for Each Stage
# ---------------------------------------------------------------------
# These functions are invoked by agents to persist structured artefacts
# into shared_context and to advance the workflow stage.

# ------------------ Draft ------------------
class ReportDraft(BaseModel):
    title: str = Field(..., description="Report title")
    content: str = Field(..., description="Full text content of the draft")

def submit_report_draft(
    title: Annotated[str, "Report title"],
    content: Annotated[str, "Full text content of the draft"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Persist the initial synthesized draft and advance to REVIEW.
    """
    report_draft = ReportDraft(
        title=title,
        content=content
    )
    context_variables["report_draft"] = report_draft.model_dump()
    context_variables["current_stage"] = ReportStage.REVIEW.value  # Drives OnContextCondition to the next agent

    return ReplyResult(
        message="Report draft submitted. Moving to review stage.",
        context_variables=context_variables,
    )

# ------------------ Feedback ------------------
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
    Persist structured review feedback and advance to REVISE.
    """
    feedback = FeedbackCollection(
        items=items,
        overall_assessment=overall_assessment,
        priority_issues=priority_issues,
        iteration_needed=iteration_needed
    )
    context_variables["feedback_collection"] = feedback.model_dump()
    context_variables["iteration_needed"] = feedback.iteration_needed
    context_variables["current_stage"] = ReportStage.REVISE.value  # Drives OnContextCondition to the next agent

    return ReplyResult(
        message="Feedback submitted. Moving to revision stage.",
        context_variables=context_variables,
    )

# ------------------ Revision ------------------
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
    Persist the revised draft; either loop back to REVIEW (if iteration still
    needed and under max_iterations) or advance to FINALIZE.
    """
    revised = RevisedReport(
        title=title,
        content=content,
        changes_made=changes_made,
    )
    context_variables["revised_report"] = revised.model_dump()

    # Loop control: either another review round or finalize
    if context_variables["iteration_needed"] and context_variables["current_iteration"] < context_variables["max_iterations"]:
        context_variables["current_iteration"] += 1
        context_variables["current_stage"] = ReportStage.REVIEW.value

        # Prepare the next review cycle with the updated draft
        context_variables["report_draft"] = {
            "title": revised.title,
            "content": revised.content,
        }

        return ReplyResult(
            message=f"Report revised. Starting iteration {context_variables['current_iteration']} with another review.",
            context_variables=context_variables,
        )
    else:
        # No further iterations requested or limit reached → finalize
        context_variables["current_stage"] = ReportStage.FINALIZE.value  # Drives OnContextCondition to the next agent

        return ReplyResult(
            message="Revisions complete. Moving to report finalization.",
            context_variables=context_variables,
        )

# ------------------ Finalization ------------------
class FinalReport(BaseModel):
    title: str = Field(..., description="Final report title")
    content: str = Field(..., description="Full text content of the final report")

def finalize_report(
    title: Annotated[str, "Final report title"],
    content: Annotated[str, "Full text content of the final report"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Persist the final report, mark iteration as complete, and terminate workflow.
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

# ---------------------------------------------------------------------
# Agent Definitions
# ---------------------------------------------------------------------
with llm_config:
    # entry_agent: flip shared state to begin the CREATE stage.
    entry_agent = ConversableAgent(
        name="entry_agent",
        system_message="""You are the entry point for the report creation process.
        Your task is to receive report creation requests and start the process.

        Use the start_report_creation_process tool to begin the process.""",
        functions=[start_report_creation_process]
    )

    # report_draft_agent: reads per-session reports + task instructions to write the first synthesized draft.
    # NOTE: System prompt mentions read_session_reports in prose, but the actual tool is read_fg_reports().
    report_draft_agent = ConversableAgent(
        name="report_draft_agent",
        
        system_message="""You are the report draft agent for the report creation process.
                Your task is to draft the report and store it in the shared context.""",
        functions=[submit_report_draft, read_task_instructions, read_fg_reports], 
        update_agent_state_before_reply=[
            UpdateSystemMessage(
        
                """
                
                ROLE
                You are the report draft agent for the report creation process.

                YOUR TASK  
                Produce the first complete draft of the final synthesized focus group report, fully compliant 
                with the task instructions.
                Submit the draft report for review.

                TOOLS  
                • read_session_reports() - Load the individual focus group session reports.  
                • read_task_instructions() - Load the task instructions that defines report requirements.  
                • submit_report_draft() - Submit the finished report draft.

                WORKFLOW (complete in order)  
                1. **Gather Source Material**  
                   a. Call **read_session_reports** tool and study the individual focus group session reports.  
                   b. Call **read_task_instructions** tool and internalize every requirement.

                2. **Write the Draft Report**  
                   • Follow the exact structure, quote-integration rules, and formatting constraints in the task instructions.  
                   • Base the report explicitly on the individual focus group session reports.  

                3. **Submit**  
                   • After you have completed the report draft, use the **submit_report_draft** tool to submit it for review.
    

                """
            ) 
        ]
     )

    # review_agent: evaluates the synthesized draft against instructions and the session reports; submits structured feedback.
    # NOTE: System prompt mentions read_session_reports in prose; tool is read_fg_reports().
    review_agent = ConversableAgent(
        name="review_agent",
        system_message="You are the report review agent responsible for critical evaluation.",
        functions=[submit_feedback, read_fg_reports, read_task_instructions],
        update_agent_state_before_reply=[
            UpdateSystemMessage(
        
                """
                ROLE
                You are the report review agent responsible for critical evaluation.

                YOUR TASK  
                Perform a rigorous, constructive evaluation of the draft synthesized, final synthesized focus group report to ensure 
                it fully satisfies the original task instructions and accurately reflects the individual focus group session reports.
                Submit your feedback for revision.

                TOOLS  
                • read_session_reports() - Load the individual focus group session reports.  
                • read_task_instructions() - Load the original task instructions (used to create the report)  
                • submit_feedback() - Submit structured feedback.

                WORKFLOW-(complete in order)  
                1. **Gather Context**  
                   a. Call **read_session_reports** to review the individual focus group session reports.  
                   b. Call **read_task_instructions** to inspect the task instructions (used to create the report).
                   c. Review the report draft : {report_draft}  

                2. **Evaluate the Draft Report** against:  
                   • Instruction compliance & completeness  
                   • Thematic accuracy and evidence support (quotes, timestamps, attributions)  
                   • Clarity, logic, and flow of writing  
                   • Neutrality and stakeholder-friendliness  

                3. **Provide Feedback**
                For the feedback you MUST provide the following:
                    1. items: list of feedback items (see next section for the collection of feedback items)
                    2. overall_assessment: Overall assessment of the document
                    3. priority_issues: List of priority issues to address
                    4. iteration_needed: Whether another iteration is needed (True or False)

                    For each item within feedback, you MUST provide the following:
                        1. section: The specific section the feedback applies to
                        2. feedback: Detailed feedback explaining the issue
                        3. severity: Rate as 'minor', 'moderate', 'major', or 'critical'
                        4. recommendation: A clear, specific action to address the feedback

                    Provide specific feedback with examples and clear recommendations for improvement.
                    For each feedback item, specify which section it applies to and rate its severity.

                    If this is a subsequent review iteration, also evaluate how well previous feedback was addressed.

                4. **Submit Feedback**
                - Use the submit_feedback tool when your review is complete, indicating whether another iteration is needed.

                """
            ) 
        ]
     )

    # revision_agent: implements feedback, tracks changes, and either loops or advances to finalize.
    revision_agent = ConversableAgent(
        name="revision_agent",
        system_message="""
        
        ROLE 
        You are the report revision agent responsible for implementing feedback.

        OBJECTIVE  
        Incorporate reviewer feedback to produce an improved Markdown report that still satisfies the original task instructions.

        INPUTS  
        • Current report draft: {report_draft} 
        • Feedback from review_agent: {feedback_collection} 

        TOOLS 
        • read_task_instructions() - Load the original task instructions (used to create the report)  
        • submit_revised_report() - Submit the revised report.


        WORKFLOW (complete in order)  
        1. **Analyze Feedback**  
           • Sort feedback items by the reviewer's stated priority (or severity if no explicit order).  
           • Verify whether any item conflicts with task instructions; if so, favor task instructions and note the conflict in the change log.

        2. **Revise the Report**  
           • Make targeted edits that directly address each feedback item.  
           • Preserve existing strengths and accurate content.  
           • Maintain all formatting constraints (e.g., no triple back-ticks; end with “# End of Report”).

        3. **Document Changes**  
           • Track and document the changes you make in a change log.

        4. **Submit**  
           • Use the submit_revised_report tool to submit the revised report, as well as the change log. The report may go through
            multiple revision cycles depending on the feedback.

         
        """,
        functions=[submit_revised_report, read_task_instructions]
    )

    # finalization_agent: performs last-mile polish + compliance check, then submits the final artifact.
    finalization_agent = ConversableAgent(
        name="finalization_agent",
        system_message="""
        
        ROLE
        You are the report finalization agent responsible for completing the process.

        YOUR TASK:   
        Produce a polished, delivery-ready Markdown report.

        INPUTS  
        • {report_draft} - the latest report version.  
        • {feedback_collection} - the revision history.

        TOOLS
        • read_task_instructions() - Load the original task instructions (used to create the report)    
        • finalize_report() - Submit the finished artefacts.

        WORKFLOW (complete in order)  
        1. **Assess Compliance**  
           • Compare {report_draft} to the original task instructions; confirm every requirement is met.  
           • Skim revision history {feedback_collection} to verify previous feedback was resolved.

        2. **Polish the Report**  
           • Correct residual issues in clarity, grammar, tone, or Markdown formatting.  
           • Preserve analyst content; limit edits to minor improvements (no structural overhauls).  
           • Ensure no triple back-ticks, proper headings, and that the document ends with “# End of Report”.

        3. **Craft Revision Journey Summary**  
           • 1-2 short paragraphs highlighting key iterations and how the report improved.

        4. **Submit Final Report**
        - Use the finalize_report tool when the report is complete and ready for delivery.

        
        """,
        functions=[finalize_report, read_task_instructions]
    )

# ---------------------------------------------------------------------
# User Agent: non-executing proxy (for logging/visibility in the pattern)
# ---------------------------------------------------------------------
user = UserProxyAgent(
    name="user",
    code_execution_config=False
)

# ---------------------------------------------------------------------
# Handoff Rules (Context-Driven Routing Between Agents)
# ---------------------------------------------------------------------
# Each rule inspects the shared context and routes control to the next agent.
# after_work behavior clarifies where control goes once an agent completes.

# Entry agent → Draft agent when loop has started and stage == CREATE
entry_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(report_draft_agent),
        condition=ExpressionContextCondition(ContextExpression("${loop_started} == True and ${current_stage} == 'create'"))
    )
)
entry_agent.handoffs.set_after_work(RevertToUserTarget())

# Draft agent → Review agent when stage == REVIEW
report_draft_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(review_agent),
        condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'review'"))
    )
)
report_draft_agent.handoffs.set_after_work(RevertToUserTarget())

# Review agent → Revision agent when stage == REVISE
review_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(revision_agent),
        condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'revise'"))
    )
)
review_agent.handoffs.set_after_work(RevertToUserTarget())

# Revision agent → either Finalization (stage == FINALIZE) or back to Review (stage == REVIEW)
revision_agent.handoffs.add_context_conditions(
    [
        OnContextCondition(
            target=AgentTarget(finalization_agent),
            condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'finalize'"))
        ),
        OnContextCondition(
            target=AgentTarget(review_agent),
            condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'review'"))
        )
    ]
)
# Default after_work nudges toward finalization once revision is done.
revision_agent.handoffs.set_after_work(AgentTarget(finalization_agent)) 

# Finalization agent terminates the workflow to signal completion.
finalization_agent.handoffs.set_after_work(TerminateTarget())

# ---------------------------------------------------------------------
# Entrypoint (run the feedback loop for the final synthesized report)
# ---------------------------------------------------------------------
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
        context_variables=shared_context,
        user_agent=user,
    )

    chat_result, final_context, last_agent = initiate_group_chat(
        pattern=agent_pattern,
        messages="Write a final report that synthesizes the results of multiple focus group session reports.",
        max_rounds=50, 
    )

    if final_context.get("final_report"):
        print("Report creation completed successfully!")

        final_report_content = final_context['final_report'].get('content', '')
       
        # Persist final synthesized report
        os.makedirs("reports", exist_ok=True)
        with open("reports/final_unified_fg_report.md", "w", encoding="utf-8") as f:
            f.write(final_report_content)

    else:
        print("Report creation did not complete successfully.")
        if final_context.get("has_error"):
            print(f"Error during {final_context.get('error_stage')} stage: {final_context.get('error_message')}")



