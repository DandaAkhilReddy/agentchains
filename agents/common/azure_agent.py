"""Azure OpenAI agent with function calling — replaces Google ADK Agent.

Uses the OpenAI Python SDK with Azure configuration. Auto-converts Python
tool functions to OpenAI function definitions and runs the standard agent loop:
send messages -> get tool_calls -> execute -> send results -> repeat.
"""

import inspect
import json
import os
from typing import Callable

from openai import AzureOpenAI


class AzureAgent:
    """Agent powered by Azure OpenAI chat completions with function calling."""

    def __init__(
        self,
        name: str,
        description: str,
        instruction: str,
        tools: list[Callable],
        model: str | None = None,
    ):
        self.name = name
        self.description = description
        self.instruction = instruction
        self._tool_map: dict[str, Callable] = {fn.__name__: fn for fn in tools}
        self._tool_defs = [self._fn_to_tool_def(fn) for fn in tools]

        self._client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
        self._model = model or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    def run(self, user_message: str, max_turns: int = 10) -> str:
        """Run the agent loop for a user message. Returns final text response."""
        messages = [
            {"role": "system", "content": self.instruction},
            {"role": "user", "content": user_message},
        ]

        for _ in range(max_turns):
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=self._tool_defs if self._tool_defs else None,
                tool_choice="auto",
            )

            choice = response.choices[0]
            msg = choice.message

            # If no tool calls, return the text response
            if not msg.tool_calls:
                return msg.content or ""

            # Append assistant message with tool calls
            messages.append(msg.model_dump())

            # Execute each tool call and append results
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}

                fn = self._tool_map.get(fn_name)
                if fn is None:
                    result = json.dumps({"error": f"Unknown tool: {fn_name}"})
                else:
                    try:
                        result = fn(**fn_args)
                        if not isinstance(result, str):
                            result = json.dumps(result, default=str)
                    except Exception as e:
                        result = json.dumps({"error": f"{type(e).__name__}: {e}"})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        return "Agent reached maximum turns without completing."

    @staticmethod
    def _fn_to_tool_def(fn: Callable) -> dict:
        """Convert a Python function to an OpenAI function tool definition."""
        sig = inspect.signature(fn)
        doc = inspect.getdoc(fn) or ""

        # Parse docstring for parameter descriptions
        param_docs = {}
        if "Args:" in doc:
            args_section = doc.split("Args:")[1]
            if "Returns:" in args_section:
                args_section = args_section.split("Returns:")[0]
            for line in args_section.strip().split("\n"):
                line = line.strip()
                if ":" in line:
                    pname, pdesc = line.split(":", 1)
                    param_docs[pname.strip()] = pdesc.strip()

        # Build parameter properties from type annotations
        properties = {}
        required = []
        for pname, param in sig.parameters.items():
            ann = param.annotation
            prop: dict = {"description": param_docs.get(pname, "")}

            if ann == str or ann == inspect.Parameter.empty:
                prop["type"] = "string"
            elif ann == int:
                prop["type"] = "integer"
            elif ann == float:
                prop["type"] = "number"
            elif ann == bool:
                prop["type"] = "boolean"
            elif ann == list or (hasattr(ann, "__origin__") and ann.__origin__ is list):
                prop["type"] = "array"
                prop["items"] = {"type": "string"}
            elif ann == dict:
                prop["type"] = "object"
            else:
                prop["type"] = "string"

            if param.default is inspect.Parameter.empty:
                required.append(pname)

            properties[pname] = prop

        fn_desc = doc.split("\n")[0] if doc else fn.__name__

        return {
            "type": "function",
            "function": {
                "name": fn.__name__,
                "description": fn_desc,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
