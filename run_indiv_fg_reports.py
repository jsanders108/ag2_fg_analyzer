# ---------------------------------------------------------------------
# Feedback Loop Pattern for Iterative Document Refinement (AG2)
# ---------------------------------------------------------------------
# This script implements a multi-agent workflow for creating, reviewing,
# revising, and finalizing focus group reports using the AG2 framework.
#
# Pattern:
#   1. Entry Agent starts the loop based on a user request.
#   2. Report Draft Agent produces the first draft using transcript + instructions.
#   3. Review Agent critically evaluates the draft and provides structured feedback.
#   4. Revision Agent applies the feedback, possibly triggering another review cycle.
#   5. Finalization Agent polishes and delivers the final report.
#
# The loop can iterate multiple times until the feedback requirements are met
# or the maximum iteration limit is reached.
#
# Key Features:
#   • Shared ContextVariables object tracks loop state and report versions.
#   • Context-driven handoffs determine which agent acts next.
#   • Modular, testable helper functions for file I/O and state updates.
#   • Structured Pydantic models ensure all stages pass validated data.
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
from autogen.agentchat.group import (
    AgentTarget,
    ContextVariables,
    ReplyResult,
    TerminateTarget,
    OnContextCondition,
    ExpressionContextCondition,
    RevertToUserTarget,
)
from autogen.agentchat.group.patterns import DefaultPattern

from dotenv import load_dotenv
import os

# Load environment variables (e.g., OpenAI API key)
load_dotenv()

# ---------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------
# LLMConfig is shared across all agents so they use the same model and parameters.
# "tool_choice" is set to "required" to ensure function-calling workflow is followed.
llm_config = LLMConfig(
    api_type="openai",
    # model="gpt-4.1",  # Full model (commented out here)
    model="gpt-4.1-mini",  # Lightweight variant for faster iteration
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0,         # Deterministic output for consistency
    cache_seed=None,
    parallel_tool_calls=False,
    tool_choice="required" # Enforces structured function call sequence
)

# ---------------------------------------------------------------------
# Workflow Stages (Enum)
# ---------------------------------------------------------------------
# Used to drive the OnContextCondition routing logic between agents.
class ReportStage(str, Enum):
    CREATE = "create"     # Drafting phase
    REVIEW = "review"     # Feedback phase
    REVISE = "revise"     # Revision phase
    FINALIZE = "finalize" # Completion phase

# ---------------------------------------------------------------------
# Initial Shared Context
# ---------------------------------------------------------------------
# This state dictionary is copied into a fresh ContextVariables object
# for each run so that agents can share data and control flow.
INITIAL_CONTEXT = {
    # Feedback loop state
    "loop_started": False,
    "current_iteration": 0,
    "max_iterations": 2,       # Limit iterations to prevent infinite loops
    "iteration_needed": True,
    "current_stage": ReportStage.CREATE,

    # Report content at various stages
    "report_draft": {},
    "feedback_collection": {},
    "revised_report": {},
    "final_report": {},

    # Error tracking
    "has_error": False,
    "error_message": "",
    "error_stage": "",
}

def make_context() -> ContextVariables:
    """
    Create a fresh ContextVariables object for a new run.
    Uses a shallow copy of INITIAL_CONTEXT to isolate state between runs.
    """
    return ContextVariables(data=INITIAL_CONTEXT.copy())

# ---------------------------------------------------------------------
# File I/O Functions
# ---------------------------------------------------------------------
# Agents call these to load their source material.
# If files are missing, error state is recorded in context so that
# agents (or the main process) can handle it gracefully.

def read_transcript(context_variables: ContextVariables,
                    session_num: Optional[int] = None) -> str:
    """
    Load the transcript for the given focus group session.
    Looks up session_num from context if not explicitly provided.
    Raises FileNotFoundError if transcript is missing.
    """
    session = session_num or context_variables.get("session_num")
    file_path = f"transcripts/fg_{session}_transcript.txt"
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError as err:
        context_variables["has_error"] = True
        context_variables["error_stage"] = "read_transcript"
        context_variables["error_message"] = str(err)
        raise

def read_task_instructions(context_variables: ContextVariables) -> str:
    """
    Load the task instructions (Markdown) for creating the individual focus group report.
    Raises FileNotFoundError if instructions are missing.
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

# ---------------------------------------------------------------------
# Stage Transition Functions
# ---------------------------------------------------------------------

def start_report_creation_process(context_variables: ContextVariables) -> ReplyResult:
    """
    Initialize loop state and trigger the CREATE stage.
    Called by entry_agent after receiving a report creation request.
    """
    context_variables["loop_started"] = True
    context_variables["current_stage"] = ReportStage.CREATE.value
    context_variables["current_iteration"] = 1

    return ReplyResult(
        message="Report creation process started.",
        context_variables=context_variables,
    )

# ---------------------------------------------------------------------
# Data Models & Submission Functions for Each Stage
# ---------------------------------------------------------------------

# ------------------
# Draft Submission
# ------------------
class ReportDraft(BaseModel):
    title: str = Field(..., description="Report title")
    content: str = Field(..., description="Full text content of the draft")

def submit_report_draft(
    title: Annotated[str, "Report title"],
    content: Annotated[str, "Full text content of the draft"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Save the initial report draft to context and move workflow to REVIEW stage.
    """
    report_draft = ReportDraft(title=title, content=content)
    context_variables["report_draft"] = report_draft.model_dump()
    context_variables["current_stage"] = ReportStage.REVIEW.value

    return ReplyResult(
        message="Report draft submitted. Moving to review stage.",
        context_variables=context_variables,
    )

# ------------------
# Feedback Submission
# ------------------
class FeedbackItem(BaseModel):
    section: str
    feedback: str
    severity: str  # minor | moderate | major | critical
    recommendation: Optional[str]

class FeedbackCollection(BaseModel):
    items: list[FeedbackItem]
    overall_assessment: str
    priority_issues: list[str]
    iteration_needed: bool

def submit_feedback(
    items: Annotated[list[FeedbackItem], "Collection of feedback items"],
    overall_assessment: Annotated[str, "Overall assessment of the report"],
    priority_issues: Annotated[list[str], "List of priority issues to address"],
    iteration_needed: Annotated[bool, "Whether another iteration is needed"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Save structured feedback to context and move workflow to REVISE stage.
    """
    feedback = FeedbackCollection(
        items=items,
        overall_assessment=overall_assessment,
        priority_issues=priority_issues,
        iteration_needed=iteration_needed
    )
    context_variables["feedback_collection"] = feedback.model_dump()
    context_variables["iteration_needed"] = feedback.iteration_needed
    context_variables["current_stage"] = ReportStage.REVISE.value

    return ReplyResult(
        message="Feedback submitted. Moving to revision stage.",
        context_variables=context_variables,
    )

# ------------------
# Revision Submission
# ------------------
class RevisedReport(BaseModel):
    title: str
    content: str
    changes_made: Optional[list[str]]

def submit_revised_report(
    title: Annotated[str, "Report title"],
    content: Annotated[str, "Full text content after revision"],
    changes_made: Annotated[Optional[list[str]], "List of changes made based on feedback"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Save revised report and determine whether to loop back to review
    or proceed to finalization.
    """
    revised = RevisedReport(title=title, content=content, changes_made=changes_made)
    context_variables["revised_report"] = revised.model_dump()

    if context_variables["iteration_needed"] and context_variables["current_iteration"] < context_variables["max_iterations"]:
        # Trigger another review cycle
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
        # End revisions and move to finalization
        context_variables["current_stage"] = ReportStage.FINALIZE.value
        return ReplyResult(
            message="Revisions complete. Moving to report finalization.",
            context_variables=context_variables,
        )

# ------------------
# Finalization Submission
# ------------------
class FinalReport(BaseModel):
    title: str
    content: str

def finalize_report(
    title: Annotated[str, "Final report title"],
    content: Annotated[str, "Full text content of the final report"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Save final report, mark loop complete, and terminate workflow.
    """
    final = FinalReport(title=title, content=content)
    context_variables["final_report"] = final.model_dump()
    context_variables["iteration_needed"] = False

    return ReplyResult(
        message="Report finalized ✅ - terminating workflow.",
        target=TerminateTarget(),
        context_variables=context_variables,
    )

with llm_config:
    # -----------------------------------------------------------------
    # Agent: entry_agent
    # -----------------------------------------------------------------
    entry_agent = ConversableAgent(
        name="entry_agent",
        system_message="""You are the entry point for the report creation process.
        Your task is to receive report creation requests and start the process.

        Use the start_report_creation_process tool to begin the process.""",
        functions=[start_report_creation_process]
    )

    # -----------------------------------------------------------------
    # Agent: report_draft_agent
    # -----------------------------------------------------------------
    report_draft_agent = ConversableAgent(
        name="report_draft_agent",
        system_message="""You are the report draft agent for the report creation process.
        Your task is to draft the report and store it in the shared context.""",
        functions=[submit_report_draft, read_transcript, read_task_instructions], 
        update_agent_state_before_reply=[
            UpdateSystemMessage(
                """
                ROLE
                You are the report draft agent for the report creation process.

                YOUR TASK  
                Produce the first complete Markdown draft of the online session report, fully compliant with the task instructions.
                Submit the draft report for review.

                TOOLS  
                • read_transcript()  
                • read_task_instructions()  
                • submit_report_draft()  

                WORKFLOW  
                1. Gather source material with read_transcript + read_task_instructions.  
                2. Write the draft according to requirements.  
                3. Submit via submit_report_draft().
                """
            ) 
        ]
     )

    # -----------------------------------------------------------------
    # Agent: review_agent
    # -----------------------------------------------------------------
    review_agent = ConversableAgent(
        name="review_agent",
        system_message="You are the report review agent responsible for critical evaluation.",
        functions=[submit_feedback, read_transcript, read_task_instructions],
        update_agent_state_before_reply=[
            UpdateSystemMessage(
                """
                ROLE
                Critical evaluator of the draft report.

                TASK  
                Compare the draft with transcript + instructions.
                Provide structured, actionable feedback.

                TOOLS  
                • read_transcript()  
                • read_task_instructions()  
                • submit_feedback()  
                """
            ) 
        ]
     )

    # -----------------------------------------------------------------
    # Agent: revision_agent
    # -----------------------------------------------------------------
    revision_agent = ConversableAgent(
        name="revision_agent",
        system_message="""
        ROLE 
        Implements review feedback into a new draft.
        OBJECTIVE  
        Improve the report while following instructions.
        TOOLS 
        • read_task_instructions()  
        • submit_revised_report()  
        """,
        functions=[submit_revised_report, read_task_instructions]
    )

    # -----------------------------------------------------------------
    # Agent: finalization_agent
    # -----------------------------------------------------------------
    finalization_agent = ConversableAgent(
        name="finalization_agent",
        system_message="""
        ROLE
        Final compliance check and polish before delivery.
        TOOLS
        • read_task_instructions()  
        • finalize_report()  
        """,
        functions=[finalize_report, read_task_instructions]
    )

# ---------------------------------------------------------------------
# User Agent
# ---------------------------------------------------------------------
user = UserProxyAgent(
    name="user",
    code_execution_config=False
)

# ---------------------------------------------------------------------
# Handoffs
# ---------------------------------------------------------------------
entry_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(report_draft_agent),
        condition=ExpressionContextCondition(ContextExpression("${loop_started} == True and ${current_stage} == 'create'"))
    )
)
entry_agent.handoffs.set_after_work(RevertToUserTarget())

report_draft_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(review_agent),
        condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'review'"))
    )
)
report_draft_agent.handoffs.set_after_work(RevertToUserTarget())

review_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(revision_agent),
        condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'revise'"))
    )
)
review_agent.handoffs.set_after_work(RevertToUserTarget())

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
revision_agent.handoffs.set_after_work(AgentTarget(finalization_agent)) 

finalization_agent.handoffs.set_after_work(TerminateTarget())

# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------
def run_indiv_fg_reports(session_num: int): 
    """Run the feedback loop pattern for report creation with iterative refinement."""
    print("Initiating Feedback Loop Pattern for Report Creation...")

    ctx = make_context()
    ctx["session_num"] = session_num   

    agent_pattern = DefaultPattern(
        initial_agent=entry_agent,
        agents=[entry_agent, report_draft_agent, review_agent, revision_agent, finalization_agent],
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
        final_report_content = final_context['final_report'].get('content', '')
        os.makedirs("reports", exist_ok=True)
        with open(f"reports/fg_{session_num}_report.md", "w", encoding="utf-8") as f:
            f.write(final_report_content)
    else:
        print("Report creation did not complete successfully.")
        if final_context.get("has_error"):
            print(f"Error during {final_context.get('error_stage')} stage: {final_context.get('error_message')}")


