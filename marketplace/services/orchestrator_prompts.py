"""Structured prompts for the LangGraph-powered SmartOrchestrator.

Each constant is a prompt template used by a specific LangGraph node.
Prompts are designed to work with GPT-4 / Claude and return structured JSON.
"""

from __future__ import annotations

DECOMPOSE_TASK_PROMPT = """You are a task decomposition expert for an AI agent orchestration platform.

Given a user task description, break it into atomic sub-tasks. Each sub-task must map to
exactly ONE agent capability type. Order the sub-tasks to respect data-flow dependencies.

Capability types available:
- "data"       — fetch, search, retrieve, crawl, or look up information
- "transform"  — translate, summarize, parse, convert, or extract structured content
- "analysis"   — analyze, evaluate, forecast, predict, or generate insights
- "compliance" — check regulatory rules, run KYC/AML, audit, or verify legal constraints
- "output"     — generate a report, send notification, export, or visualize results

Rules:
1. Every sub-task must have a unique id (t1, t2, …).
2. depends_on lists ids of sub-tasks that must complete before this one starts.
3. Use only the five capability types listed above.
4. Aim for 2–6 sub-tasks; do not over-decompose simple tasks.
5. Return ONLY valid JSON — no markdown, no explanation.

Task description: {task_description}

Return JSON in this exact schema:
{{
  "sub_tasks": [
    {{
      "id": "t1",
      "description": "Fetch current market prices for the requested assets",
      "depends_on": [],
      "required_capability": "data"
    }},
    {{
      "id": "t2",
      "description": "Analyse price trends and generate forecast",
      "depends_on": ["t1"],
      "required_capability": "analysis"
    }}
  ]
}}"""


MATCH_AGENTS_PROMPT = """You are an agent matching expert for an AI agent marketplace.

Your job is to assign the best available agent to each sub-task based on the agent's
capabilities, reputation score, and cost. Choose agents that directly match the required
capability type for each sub-task.

Sub-tasks:
{sub_tasks_json}

Available agents (ordered by rank score, highest first):
{agents_json}

Assignment rules:
1. Each sub-task MUST get exactly one agent assignment.
2. Prefer agents whose capabilities or description explicitly match the sub-task.
3. If multiple agents match, prefer higher rank_score.
4. If no agent matches a sub-task, assign the highest-ranked agent overall and note the mismatch in "reason".
5. "skill_id" should be "default" unless the agent's description indicates a specific skill name.
6. Return ONLY valid JSON — no markdown, no explanation.

Return JSON in this exact schema:
{{
  "assignments": [
    {{
      "task_id": "t1",
      "agent_name": "DataFetchAgent",
      "agent_id": "uuid-of-agent",
      "skill_id": "default",
      "reason": "Best match for data fetching based on capabilities"
    }}
  ]
}}"""


BUILD_DAG_PROMPT = """You are a DAG (Directed Acyclic Graph) builder for an AI agent orchestration engine.

Given the following task assignments, construct a valid execution DAG. Each node represents
one agent call. Edges encode execution order from the sub-task dependencies.

Task assignments:
{assignments_json}

Sub-tasks with dependencies:
{sub_tasks_json}

DAG construction rules:
1. Each assignment becomes one node. Node id = "node_<task_id>" (e.g. "node_t1").
2. "depends_on" in a node lists the node ids (not task ids) that must complete first.
3. "config.agent_id" must be the agent_id from the assignment.
4. "config.skill_id" must be the skill_id from the assignment.
5. "type" must always be "agent_call".
6. "edges" array is optional; dependencies can be expressed solely via "depends_on".
7. The graph must be acyclic. Validate before returning.
8. Return ONLY valid JSON — no markdown, no explanation.

Return JSON in this exact schema:
{{
  "nodes": {{
    "node_t1": {{
      "type": "agent_call",
      "config": {{
        "agent_id": "uuid-of-agent",
        "skill_id": "default"
      }},
      "depends_on": []
    }},
    "node_t2": {{
      "type": "agent_call",
      "config": {{
        "agent_id": "uuid-of-other-agent",
        "skill_id": "default"
      }},
      "depends_on": ["node_t1"]
    }}
  }},
  "edges": []
}}"""


SYNTHESIZE_RESULT_PROMPT = """You are a result synthesizer for an AI agent pipeline.

Multiple agents have completed their assigned tasks. Your job is to combine their outputs
into a single, coherent, well-structured response that directly addresses the original task.

Original task: {task_description}

Agent outputs (keyed by node id):
{outputs_json}

Synthesis guidelines:
1. Address the original task directly — do not describe the pipeline structure.
2. Combine data, analysis, and compliance findings into a cohesive narrative.
3. If any agent returned an error, note it briefly but still synthesize the available results.
4. Structure the response with clear sections if the output is long.
5. Be concise and professional — this output may be shown directly to end users.

Return a clear, well-structured response (plain text or Markdown, NOT JSON):"""
