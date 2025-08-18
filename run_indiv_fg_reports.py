# =============================================================================
# AG2 Feedback Loop Pattern for Iterative Focus Group Report Refinement
# ---------------------------------------------------------------------
# This script implements a multi-agent workflow for creating, reviewing,
# revising, and finalizing focus group reports using the AG2 framework.
# =============================================================================

from typing import Annotated, Optional
from enum import Enum
from pydantic import BaseModel
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
class ReportStage(str, Enum):
    CREATING = "creating"     
    REVIEWING = "reviewing"   
    REVISING = "revising"    
    FINALIZING = "finalizing" 
 
# ---------------------------------------------------------------------
# Initial Shared Context
# ---------------------------------------------------------------------
INITIAL_CONTEXT = {
    # Feedback loop state
    "loop_started": False,
    "current_iteration": 0,
    "max_iterations": 2,       # Limit iterations to prevent infinite loops
    "iteration_needed": True,
    "current_stage": ReportStage.CREATING.value,

    # Report content at various stages
    "report_draft": "",
    "feedback_collection": {},
    "revised_report": {},
    "final_report": "",

}

def make_context() -> ContextVariables:
    """
    Create a fresh ContextVariables object for each new run.
    Uses a shallow copy of INITIAL_CONTEXT to isolate state between runs.
    """
    return ContextVariables(data=INITIAL_CONTEXT.copy())

# ---------------------------------------------------------------------
# File I/O Functions
# ---------------------------------------------------------------------
def read_transcript(context_variables: ContextVariables,
                    session_num: Optional[int] = None) -> str:
    """
    Load the transcript for the given focus group session.
    Looks up session_num from context if not explicitly provided.
    """
    session = session_num or context_variables.get("session_num")
    file_path = f"transcripts/fg_{session}_transcript.txt"
    with open(file_path, "r", encoding="utf-8") as fh:
        return fh.read()
    

def read_task_instructions() -> str:
    """
    Load the task instructions (Markdown) for creating the individual focus group report.
    """
    file_path = "instructions/individual_fg_report_task_instructions.md"
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------
# Stage 1: Kickoff / Creation
# ---------------------------------------------------------------------
def kickoff_report_creation_process(context_variables: ContextVariables) -> ReplyResult:
    """
    Start the report creation process and advance to CREATING stage.
    """
    context_variables["loop_started"] = True
    context_variables["current_stage"] = ReportStage.CREATING.value
    context_variables["current_iteration"] = 1

    return ReplyResult(
        message="Report creation process started.",
        context_variables=context_variables,
    )


# ---------------------------------------------------------------------
# Data Models & Submission Functions for Each Stage
# ---------------------------------------------------------------------

# ------------------
# Stage 2: Drafting
# ------------------
def submit_report_draft(
    content: Annotated[str, "Full text content of the draft"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Submit the initial report draft and advance to REVIEWING stage.
    """
    context_variables["report_draft"] = content
    context_variables["current_stage"] = ReportStage.REVIEWING.value

    return ReplyResult(
        message="Report draft submitted. Moving to reviewing stage.",
        context_variables=context_variables,
    )

# ------------------
# Stage 3: Reviewing/Feedback
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
    Submit reviewer feedback and advance to revising stage.
    """
    feedback = FeedbackCollection(
        items=items,
        overall_assessment=overall_assessment,
        priority_issues=priority_issues,
        iteration_needed=iteration_needed
    )
    context_variables["feedback_collection"] = feedback.model_dump()
    context_variables["iteration_needed"] = feedback.iteration_needed
    context_variables["current_stage"] = ReportStage.REVISING.value

    return ReplyResult(
        message="Feedback submitted. Moving to revising stage.",
        context_variables=context_variables,
    )

# ------------------
# Stage 4: Revising
# ------------------
class RevisedReport(BaseModel):
    content: str
    changes_made: Optional[list[str]]

def submit_revised_report(
    content: Annotated[str, "Full text content after revision"],
    changes_made: Annotated[Optional[list[str]], "List of changes made based on feedback"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Submit revised report and either loop back to REVIEWING or advance to FINALIZING stage.
    """
    revised = RevisedReport(content=content, changes_made=changes_made)
    context_variables["revised_report"] = revised.model_dump()
    context_variables["report_draft"] = revised.content

    if context_variables["iteration_needed"] and context_variables["current_iteration"] < context_variables["max_iterations"]:
        # Trigger another review cycle
        context_variables["current_iteration"] += 1
        context_variables["current_stage"] = ReportStage.REVIEWING.value
        return ReplyResult(
            message=f"Report revised. Starting iteration {context_variables['current_iteration']} with another review.",
            context_variables=context_variables,
        )
    else:
        # End revisions and move to finalization
        context_variables["current_stage"] = ReportStage.FINALIZING.value
        return ReplyResult(
            message="Revisions complete. Moving to finalizing stage.",
            context_variables=context_variables,
        )

# ------------------
# Stage 5: Finalizing
# ------------------
def submit_final_report(
    content: Annotated[str, "Full text content of the final report"],
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Submit the final report and terminate workflow.
    """
    context_variables["final_report"] = content
    context_variables["iteration_needed"] = False
    context_variables["current_stage"] = "done"

    return ReplyResult(
        message="Report finalized ✅ - terminating workflow.",
        target=TerminateTarget(),
        context_variables=context_variables,
    )

with llm_config:
    # -----------------------------------------------------------------
    # Agent: kickoff_agent
    # -----------------------------------------------------------------
    kickoff_agent = ConversableAgent(
        name="kickoff_agent",
        system_message="""
        You are the kickoff agent. You only initialize the workflow. Your job is to call 
        kickoff_report_creation_process(context_variables: ContextVariables).

        Do not analyze data or produce narrative.
        """,
        functions=[kickoff_report_creation_process]
    )

    # -----------------------------------------------------------------
    # Agent: report_drafter_agent
    # -----------------------------------------------------------------
    report_drafter_agent = ConversableAgent(
        name="report_drafter_agent",
        system_message="""You are the report drafter agent.""",
        functions=[submit_report_draft, read_transcript, read_task_instructions], 
        update_agent_state_before_reply=[
            UpdateSystemMessage(
                """
                ROLE:
                You are the report drafter agent. Your job is to produce the first complete Markdown draft of the 
                online session report, fully compliant with the task instructions. 
                
                TOOLS:
                • read_transcript(session_num: int, context_variables: ContextVariables) - Load the full focus group session transcript. 
                • read_task_instructions() - Load the task instructions that defines report requirements. 
                • submit_report_draft(content: str, context_variables: ContextVariables) - Submit the finished report draft. 
                
                WORKFLOW (complete in order):
                1. **Gather Source Material** 
                   a. Call **read_transcript** tool and study the transcript of the focus group session. 
                   b. Call **read_task_instructions** tool and internalize every requirement. 
                2. **Write the Draft Report** 
                   • Follow the exact structure, quote-integration rules, and formatting constraints in the task instructions. 
                   • Base the report explicitly on the focus group session transcript. 

                SUBMISSION:
                After you have created the report draft, you MUST submit the report draft by using the *submit_report_draft* function.
                """
            ) 
        ]
     )

    # -----------------------------------------------------------------
    # Agent: report_reviewer_agent
    # -----------------------------------------------------------------
    report_reviewer_agent = ConversableAgent(
        name="report_reviewer_agent",
        system_message="You are the report reviewer agent.",
        functions=[submit_feedback, read_transcript, read_task_instructions],
        update_agent_state_before_reply=[
            UpdateSystemMessage(
                """
                ROLE:
                You are the report reviewer agent. Your job is to perform a rigorous, constructive evaluation of the draft 
                focus group session report to ensure it fully satisfies the original task instructions and accurately reflects 
                the transcript of the focus group session. 
                
                TOOLS:
                • read_transcript(session_num: int, context_variables: ContextVariables) - Load and inspect the full focus group session transcript. 
                • read_task_instructions() - Load the original task instructions (used to create the report) 
                • submit_feedback(items: list[FeedbackItem], overall_assessment: str, priority_issues: list[str], iteration_needed: bool, context_variables: ContextVariables) - Submit structured feedback. 
                
                WORKFLOW-(complete in order):
                1. **Gather Context** 
                   a. Call **read_transcript** to review the transcript of the focus group session. 
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
                   2. overall_assessment: Overall assessment of the document" 
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

                SUBMISSION:
                After you have created your feedback, you MUST use the submit_feedback function to submit the feedback.
                """
            ) 
        ]
     )

    # -----------------------------------------------------------------
    # Agent: report_reviser_agent
    # -----------------------------------------------------------------
    report_reviser_agent = ConversableAgent(
        name="report_reviser_agent",
        system_message="""
        You are the report reviser agent.
        """,
        functions=[submit_revised_report, read_task_instructions],
        update_agent_state_before_reply=[
            UpdateSystemMessage(
                """
                ROLE:
                You are the report reviser agent. Your job is to incorporate reviewer feedback to produce an improved Markdown 
                report draft that still satisfies the original task instructions. 
                
                INPUTS: 
                • Current report draft: {report_draft} 
                • Feedback from report_reviewer_agent: {feedback_collection} 
                
                TOOLS 
                • read_task_instructions() - Load the original task instructions (used to create the report) 
                • submit_revised_report(content: str, changes_made: Optional[list[str]], context_variables: ContextVariables) - Submit the revised report. 
                
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

                SUBMISSION: 
                After you have created your revised report, you MUST use the submit_revised_report function to submit the revised report,
                as well as the change log.
                The revised report may go through multiple revision cycles depending on the feedback.
                """
            ) 
        ]
    )

    # -----------------------------------------------------------------
    # Agent: final_report_agent
    # -----------------------------------------------------------------
    final_report_agent = ConversableAgent(
        name="final_report_agent",
        system_message="""
        You are the final report agent.
        """,
        functions=[submit_final_report, read_task_instructions],
        update_agent_state_before_reply=[
            UpdateSystemMessage(
                """
                ROLE:
                You are the final report agent. Your job is to complete the process by producing a polished, delivery-ready Markdown report.
                
                INPUTS: 
                • {report_draft} - the latest report version. 
                • {feedback_collection} - the revision history. 
                
                TOOLS: 
                • read_task_instructions() - Load the original task instructions (used to create the report) 
                • finalize_report(content: str, context_variables: ContextVariables) - Submit the finished artefacts. 
                
                WORKFLOW (complete in order):
                1. **Assess Compliance** 
                   • Compare {report_draft} to the original task instructions; confirm every requirement is met. 
                   • Skim revision history {feedback_collection} to verify previous feedback was resolved. 
                2. **Polish the Report** 
                   • Correct residual issues in clarity, grammar, tone, or Markdown formatting. 
                   • Preserve analyst content; limit edits to minor improvements (no structural overhauls). 
                   • Ensure no triple back-ticks, proper headings, and that the document ends with “# End of Report”. 
                3. **Craft Revision Journey Summary** 
                   • 1-2 short paragraphs highlighting key iterations and how the report improved. 

                SUBMISSION:
                After you have created your final report, you MUST use the submit_final_report function to submit the final report.
                """
            )
        ]
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
kickoff_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(report_drafter_agent),
        condition=ExpressionContextCondition(ContextExpression("${loop_started} == True and ${current_stage} == 'creating'"))
    )
)
kickoff_agent.handoffs.set_after_work(RevertToUserTarget())

report_drafter_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(report_reviewer_agent),
        condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'reviewing'"))
    )
)
report_drafter_agent.handoffs.set_after_work(RevertToUserTarget())

report_reviewer_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(report_reviser_agent),
        condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'revising'"))
    )
)
report_reviewer_agent.handoffs.set_after_work(RevertToUserTarget())

report_reviser_agent.handoffs.add_context_conditions(
    [
        OnContextCondition(
            target=AgentTarget(final_report_agent),
            condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'finalizing'"))
        ),
        OnContextCondition(
            target=AgentTarget(report_reviewer_agent),
            condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'reviewing'"))
        )
    ]
)
report_reviser_agent.handoffs.set_after_work(AgentTarget(final_report_agent)) 

final_report_agent.handoffs.set_after_work(TerminateTarget())

# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------
def run_indiv_fg_reports(session_num: int): 
    """Run the feedback loop pattern for report creation with iterative refinement."""
    print("Initiating Feedback Loop Pattern for Report Creation...")

    ctx = make_context()
    ctx["session_num"] = session_num   

    agent_pattern = DefaultPattern(
        initial_agent=kickoff_agent,
        agents=[kickoff_agent, report_drafter_agent, report_reviewer_agent, report_reviser_agent, final_report_agent],
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
        final_report_content = final_context['final_report']
        os.makedirs("reports", exist_ok=True)
        with open(f"reports/fg_{session_num}_report.md", "w", encoding="utf-8") as f:
            f.write(final_report_content)
    else:
        print("Report creation did not complete successfully.")
        

