"""Pipeline: chain multiple A2A agents into sequential workflows."""

import logging
from typing import Any, Callable

from agents.common.a2a_client import A2AClient

logger = logging.getLogger(__name__)


class PipelineStep:
    """A single step in a pipeline that calls one A2A agent."""

    def __init__(
        self,
        agent_url: str,
        skill_id: str,
        transform_fn: Callable[[dict], str] | None = None,
        name: str | None = None,
        auth_token: str | None = None,
    ):
        """
        Args:
            agent_url: Base URL of the A2A agent
            skill_id: Which skill to invoke on the agent
            transform_fn: Optional function to transform previous step's result
                          into input text for this step. Default: json.dumps(result)
            name: Human-readable step name
            auth_token: Optional JWT for authenticating with this agent
        """
        self.agent_url = agent_url
        self.skill_id = skill_id
        self.transform_fn = transform_fn
        self.name = name or f"{agent_url}/{skill_id}"
        self.auth_token = auth_token


class Pipeline:
    """Chain multiple A2A agents into a sequential workflow.

    Usage:
        pipeline = Pipeline("Research Pipeline")
        pipeline.add_step("http://search-agent:9001", "web-search")
        pipeline.add_step("http://summarizer:9002", "summarize",
                         transform_fn=lambda r: r.get("text", ""))
        pipeline.add_step("http://knowledge:9003", "store")

        result = await pipeline.execute("Find the latest Python trends")
    """

    def __init__(self, name: str = "Pipeline"):
        self.name = name
        self.steps: list[PipelineStep] = []

    def add_step(
        self,
        agent_url: str,
        skill_id: str,
        transform_fn: Callable[[dict], str] | None = None,
        name: str | None = None,
        auth_token: str | None = None,
    ) -> "Pipeline":
        """Add a step to the pipeline.

        Args:
            agent_url: A2A agent base URL
            skill_id: Skill to invoke
            transform_fn: Transform previous output → input text
            name: Step name for logging
            auth_token: JWT for this agent

        Returns:
            self for chaining
        """
        step = PipelineStep(
            agent_url=agent_url,
            skill_id=skill_id,
            transform_fn=transform_fn,
            name=name,
            auth_token=auth_token,
        )
        self.steps.append(step)
        return self

    async def execute(self, initial_input: str) -> dict:
        """Execute the pipeline sequentially, passing each result to the next step.

        Args:
            initial_input: Input text for the first step

        Returns:
            Dict with final_result, steps (with individual results), and status
        """
        if not self.steps:
            return {"error": "Pipeline has no steps", "status": "failed"}

        results: list[dict[str, Any]] = []
        current_input = initial_input

        for i, step in enumerate(self.steps):
            step_name = step.name or f"Step {i+1}"
            logger.info("Pipeline '%s': executing %s", self.name, step_name)

            try:
                client = A2AClient(
                    base_url=step.agent_url,
                    auth_token=step.auth_token,
                )

                task_result = await client.send_task(
                    skill_id=step.skill_id,
                    message=current_input,
                )

                step_output = {
                    "step": i + 1,
                    "name": step_name,
                    "agent_url": step.agent_url,
                    "skill_id": step.skill_id,
                    "state": task_result.get("state", "unknown"),
                    "result": task_result,
                }
                results.append(step_output)

                # Check for failure
                if task_result.get("state") == "failed":
                    logger.error(
                        "Pipeline '%s': step %s failed — %s",
                        self.name, step_name, task_result.get("error"),
                    )
                    return {
                        "status": "failed",
                        "failed_at_step": i + 1,
                        "error": task_result.get("error", "Step failed"),
                        "steps": results,
                    }

                # Transform result for next step
                if i < len(self.steps) - 1:
                    if step.transform_fn:
                        current_input = step.transform_fn(task_result)
                    else:
                        # Default: extract text from first artifact
                        artifacts = task_result.get("artifacts", [])
                        if artifacts:
                            parts = artifacts[0].get("parts", [])
                            for part in parts:
                                if part.get("type") == "text":
                                    current_input = part.get("text", "")
                                    break
                        else:
                            import json
                            current_input = json.dumps(task_result)

            except Exception as e:
                logger.error(
                    "Pipeline '%s': step %s exception — %s",
                    self.name, step_name, e,
                )
                results.append({
                    "step": i + 1,
                    "name": step_name,
                    "agent_url": step.agent_url,
                    "skill_id": step.skill_id,
                    "state": "error",
                    "error": str(e),
                })
                return {
                    "status": "failed",
                    "failed_at_step": i + 1,
                    "error": str(e),
                    "steps": results,
                }

        logger.info("Pipeline '%s': completed all %d steps", self.name, len(self.steps))
        return {
            "status": "completed",
            "final_result": results[-1]["result"] if results else None,
            "steps": results,
            "total_steps": len(self.steps),
        }

    def __repr__(self) -> str:
        step_names = [s.name for s in self.steps]
        return f"Pipeline(name={self.name!r}, steps={step_names})"
