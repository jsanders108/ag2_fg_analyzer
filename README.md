# AG2: Focus Group Transcript Analyzer

## Overview & Background
This project shows how **AG2 agents** can help market researchers analyze multiple focus group session transcripts and generate a final, unified report. In this example, **two mock focus-group sessions** about a premium concept, **white strawberries**, are analyzed. The transcripts are **synthetic (AI-generated)** and designed to mimic realistic qualitative data.

**Solving a Market Research Pain Point**: Traditional focus group analysis requires researchers to manually sort through pages and pages of transcripts, identifying themes, extracting relevant quotes, and synthesizing insights across sessions—a process that can take days or even weeks. This AG2 workflow automates the most time-consuming aspects of transcript analysis, transforming hours of manual work into minutes of automated processing while maintaining analytical rigor and quality.

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

## System Architecture

The AG2 workflow is built around three main components that work together to automate focus group analysis:

### 1) Entry Point (`main.py`)
Orchestrates the entire process by running individual session analyses sequentially, then synthesizing results into a unified report.

### 2) Per-Session Analysis (`run_indiv_fg_reports.py`)
Implements the iterative feedback loop for each focus group session using specialized agents:
- **Entry Agent**: Initiates the report creation process
- **Draft Agent**: Creates initial analysis by reading transcripts and task instructions
- **Review Agent**: Evaluates draft quality, coverage, and accuracy
- **Revision Agent**: Applies feedback and improves the report
- **Finalization Agent**: Produces the final session report

### 3) Unified Synthesis (`final_fg_report.py`)
Uses the same feedback loop pattern to combine individual session reports into a comprehensive analysis that compares insights across demographics and provides consolidated recommendations.

**Key Technical Features:**
- **Iterative Quality Control**: Each agent can trigger multiple review-revision cycles until quality standards are met
- **Context Sharing**: Agents maintain shared state to track progress and pass information between stages
- **File I/O Integration**: Automated reading of transcripts and writing of final reports
- **Structured Data Models**: Ensures consistent formatting and required content sections

The system processes raw transcript files and produces polished, decision-ready markdown reports without manual intervention.

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

**Time Savings & Efficiency**: What traditionally requires researchers to spend hours manually combing through transcripts, coding responses, and cross-referencing themes is now accomplished in minutes through automated agent workflows. This AG2 implementation saves significant time while maintaining the analytical depth and rigor that market research demands, allowing researchers to focus on strategic interpretation and decision-making rather than tedious transcript processing.
