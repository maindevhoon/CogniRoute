import json
from pydantic import BaseModel, Field
from typing import Dict
from .schemas import TaskGraph, WorkerResult
from .services.llm import call_model

class FixerResponse(BaseModel):
    files: Dict[str, str] = Field(
        description="Map of filename to the fully rewritten file content. Include only the files that needed fixing."
    )

class FixerAgent:
    """Uses the 32B model to globally fix cross-file issues found by the verifier."""

    async def fix(
        self,
        task_graph: TaskGraph,
        all_results: Dict[str, WorkerResult],
        issues: list[str],
        user_goal: str
    ) -> Dict[str, str]:
        files_str = ""
        for node_id, res in all_results.items():
            files_str += f"\n\n### FILE: {res.artifact.filename}\n```\n{res.artifact.content}\n```\n"

        prompt = (
            "You are the senior architect. The junior developers generated the following files for the user goal.\n"
            f"## User Goal\n{user_goal}\n\n"
            f"## Generated Files\n{files_str}\n\n"
            "## Verification Failed\n"
            "The final cross-file verification failed with the following issues:\n"
            + "\n".join(f"- {issue}" for issue in issues) + "\n\n"
            "Your task is to fix these issues. Return a JSON object mapping the filename to its COMPLETE rewritten code.\n"
            "Only include files that you modified to fix the issues.\n"
            "Do NOT include markdown fences in the JSON strings. Just return raw code in the values.\n"
            "Return ONLY valid JSON matching this schema:\n"
            '{"files": {"main.py": "import ...\\n\\n..."}}'
        )

        try:
            # We use the architect role to get the 32B reasoning model
            result = await call_model("architect", prompt, json_schema_hint='{"files": {"string": "string"}}')
            parsed = FixerResponse.model_validate_json(result.text)
            return parsed.files
        except Exception as e:
            print(f"Fixer failed: {e}")
            return {}
