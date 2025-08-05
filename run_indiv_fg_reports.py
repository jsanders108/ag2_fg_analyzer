# Feedback Loop pattern for iterative document refinement
# Each agent refines the analysis of the transcript, which is then sent back for further iterations based on feedback

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

load_dotenv()

llm_config = LLMConfig(
    api_type="openai",
    #model="gpt-4.1",
    model="gpt-4.1-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0,
    cache_seed=None,
    parallel_tool_calls=False,
    tool_choice="required" #Forces the model to call the functions that submit the report, revision, and finalization. Without this, things don't work. 
)


# Report stage tracking for the feedback loop
class ReportStage(str, Enum):
    CREATE = "create"
    REVIEW = "review"
    REVISE = "revise"
    FINALIZE = "finalize" 



# Shared context for tracking report state
INITIAL_CONTEXT = {
    # Feedback loop state 
    "loop_started": False,
    "current_iteration": 0,
    "max_iterations": 2,
    "iteration_needed": True,
    "current_stage": ReportStage.CREATE,

    # Report data at various stages
    "report_draft": {},
    "feedback_collection": {},
    "revised_report": {},
    "final_report": {},

    # Error state
    "has_error": False,
    "error_message": "",
    "error_stage": "",
}

# This resets the context for each run
def make_context() -> ContextVariables:
    # deep‑copy so each run is isolated
    return ContextVariables(data=INITIAL_CONTEXT.copy())



# Functions for the feedback loop pattern

def read_transcript(context_variables: ContextVariables,
                    session_num: Optional[int] = None) -> str:
    """
    Return the raw transcript text for the current focus group session.
    Falls back to context_variables['session_num'] if no explicit
    session_num argument is provided.
    """
    # Prefer the explicit arg (lets you unit‑test easily)
    session = session_num or context_variables.get("session_num")

    file_path = f"transcripts/fg_{session}_transcript.txt"
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError as err:
        # surface the problem via shared context so agents can react
        context_variables["has_error"]   = True
        context_variables["error_stage"] = "read_transcript"
        context_variables["error_message"] = str(err)
        raise



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




def start_report_creation_process(
    context_variables: ContextVariables
) -> ReplyResult:
    """
    Start the report creation process
    """
    context_variables["loop_started"] = True # Drives OnContextCondition to the next agent
    context_variables["current_stage"] = ReportStage.CREATE.value # Drives OnContextCondition to the next agent
    context_variables["current_iteration"] = 1

    return ReplyResult(
        message=f"Report creation process started.",
        context_variables=context_variables,
    )




# Report Drafting Stage
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
    context_variables["current_stage"] = ReportStage.REVIEW.value # Drives OnContextCondition to the next agent

    return ReplyResult(
        message="Report draft submitted. Moving to review stage.",
        context_variables=context_variables,
    )


# Report Feedback Stage
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
    feedback = FeedbackCollection(
        items=items,
        overall_assessment=overall_assessment,
        priority_issues=priority_issues,
        iteration_needed=iteration_needed
    )
    context_variables["feedback_collection"] = feedback.model_dump()
    context_variables["iteration_needed"] = feedback.iteration_needed
    context_variables["current_stage"] = ReportStage.REVISE.value # Drives OnContextCondition to the next agent

    return ReplyResult(
        message="Feedback submitted. Moving to revision stage.",
        context_variables=context_variables,
    )


# Report Revision Stage
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
    revised = RevisedReport(
        title=title,
        content=content,
        changes_made=changes_made,
    )
    context_variables["revised_report"] = revised.model_dump()

     # Check if we need another iteration or if we're done
    if context_variables["iteration_needed"] and context_variables["current_iteration"] < context_variables["max_iterations"]:
        context_variables["current_iteration"] += 1
        context_variables["current_stage"] = ReportStage.REVIEW.value

        # Update the document draft with the revised document for the next review
        context_variables["report_draft"] = {
            "title": revised.title,
            "content": revised.content,
        }

        return ReplyResult(
            message=f"Report revised. Starting iteration {context_variables['current_iteration']} with another review.",
            context_variables=context_variables,
        )
    else:
        # We're done with revisions, move to final stage
        context_variables["current_stage"] = ReportStage.FINALIZE.value # Drives OnContextCondition to the next agent

        return ReplyResult(
            message="Revisions complete. Moving to report finalization.",
            context_variables=context_variables,
        )

# Report Finalization Stage
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
    final = FinalReport(
        title=title,
        content=content,
    )
    context_variables["final_report"] = final.model_dump()
    context_variables["iteration_needed"] = False

    return ReplyResult(
        message="Report finalized ✅ - terminating workflow.",
        target=TerminateTarget(),  
        context_variables=context_variables,
    )



with llm_config:
    # Agents for the feedback loop
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
        update_agent_state_before_reply=[
            UpdateSystemMessage(
        
                """
                
                ROLE
                You are the report draft agent for the report creation process.

                YOUR TASK  
                Produce the first complete Markdown draft of the online session report, fully compliant with the task instructions.
                Submit the draft report for review.

                TOOLS  
                • read_transcript() - Load the full focus group session transcript.  
                • read_task_instructions() - Load the task instructions that defines report requirements.  
                • submit_report_draft() - Submit the finished report draft.

                WORKFLOW (complete in order)  
                1. **Gather Source Material**  
                   a. Call **read_transcript** tool and study the transcript of the focus group session.  
                   b. Call **read_task_instructions** tool and internalize every requirement.

                2. **Write the Draft Report**  
                   • Follow the exact structure, quote-integration rules, and formatting constraints in the task instructions.  
                   • Base the report explicitly on the focus group session transcript.  

                3. **Submit**  
                   • After you have completed the report draft, use the **submit_report_draft** tool to submit it for review.
    

                """
            ) 
        ]
     )


    review_agent = ConversableAgent(
        name="review_agent",
        system_message="You are the report review agent responsible for critical evaluation.",
        functions=[submit_feedback, read_transcript, read_task_instructions],
        update_agent_state_before_reply=[
            UpdateSystemMessage(
        
                """
                ROLE
                You are the report review agent responsible for critical evaluation.

                YOUR TASK  
                Perform a rigorous, constructive evaluation of the draft focus group session report to ensure it fully satisfies the original 
                task instructions and accurately reflects the transcript of the focus group session.
                Submit your feedback for revision.

                TOOLS  
                • read_transcript() - Load and inspect the full focus group session transcript.  
                • read_task_instructions() - Load the original task instructions (used to create the report)  
                • submit_feedback() - Submit structured feedback.

                WORKFLOW-(complete in order)  
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

                4. **Submit Feedback**
                - Use the submit_feedback tool when your review is complete, indicating whether another iteration is needed.

                """
            ) 
        ]
     )


    revision_agent = ConversableAgent(
        name="revision_agent",
        system_message="""
        
        ROLE 
        You are the report revision agent responsible for implementing feedback.

        OBJECTIVE  
        Incorporate reviewer feedback to produce an improved Markdown report draft that still satisfies the original task instructions.

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
           • Use the finalize_report tool when the report is complete and ready for delivery.

        
        """,
        functions=[finalize_report, read_task_instructions]
    )

# User agent for interaction
user = UserProxyAgent(
    name="user",
    code_execution_config=False
)

# Register handoffs for the feedback loop
# Entry agent starts the loop
entry_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(report_draft_agent),
        condition=ExpressionContextCondition(ContextExpression("${loop_started} == True and ${current_stage} == 'create'"))
    )
)
entry_agent.handoffs.set_after_work(RevertToUserTarget())


# Report draft agent passes to Planning agent
report_draft_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(review_agent),
        condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'review'"))
    )
)
report_draft_agent.handoffs.set_after_work(RevertToUserTarget())

# Report review agent passes to Planning agent
review_agent.handoffs.add_context_condition(
    OnContextCondition(
        target=AgentTarget(revision_agent),
        condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'revise'"))
    )
)
review_agent.handoffs.set_after_work(RevertToUserTarget())


# Revision agent passes back to Review agent or to Finalization agent
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

# Finalization agent completes the loop and terminates the workflow
# This termination allows for the program to move automatically to the next session
finalization_agent.handoffs.set_after_work(TerminateTarget())

 
# Run the feedback loop
def run_indiv_fg_reports(session_num: int): 
    """Run the feedback loop pattern for report creation with iterative refinement"""
    print("Initiating Feedback Loop Pattern for Report Creation...")

    ctx = make_context() # creates fresh state

    ctx["session_num"] = session_num   

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


    else:
        print("Report creation did not complete successfully.")
        if final_context.get("has_error"):
            print(f"Error during {final_context.get('error_stage')} stage: {final_context.get('error_message')}")


