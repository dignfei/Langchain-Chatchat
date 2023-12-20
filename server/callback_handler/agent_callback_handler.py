from __future__ import annotations
from uuid import UUID
import json
import asyncio
from typing import Any, Dict, List, Optional

from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.schema import AgentFinish, AgentAction
from langchain_core.outputs import LLMResult


def dumps(obj: Dict) -> str:
    return json.dumps(obj, ensure_ascii=False)


class AgentStatus:
    llm_start: int = 1
    llm_new_token: int = 2
    llm_end: int = 3
    agent_action: int = 4
    agent_finish: int = 5
    error: int = 6


class AgentExecutorAsyncIteratorCallbackHandler(AsyncIteratorCallbackHandler):
    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()
        self.done = asyncio.Event()
        self.out = True

    async def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        data = {
            "status" : AgentStatus.llm_start,
            "text" : "",
        }
        self.done.clear()
        self.queue.put_nowait(dumps(data))


    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        special_tokens = ["Action", "<|observation|>"]
        for stoken in special_tokens:
            if stoken in token:
                before_action = token.split(stoken)[0]
                data = {
                    "status" : AgentStatus.llm_new_token,
                    "text": before_action + "\n",
                }
                self.queue.put_nowait(dumps(data))
                self.out = False
                break

        if token is not None and token != "" and self.out:
            data = {
                "status" : AgentStatus.llm_new_token,
                "text" : token,
            }
            self.queue.put_nowait(dumps(data))

    async def on_chat_model_start(
            self,
            serialized: Dict[str, Any],
            messages: List[List],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            tags: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            **kwargs: Any,
    ) -> None:
        data = {
            "status" : AgentStatus.llm_start,
            "text" : "",
        }
        self.done.clear()
        self.queue.put_nowait(dumps(data))

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        data = {
            "status" : AgentStatus.llm_end,
            "text" : response.generations[0][0].message.content,
        }
        self.out = True
        self.queue.put_nowait(dumps(data))

    async def on_llm_error(self, error: Exception | KeyboardInterrupt, **kwargs: Any) -> None:
        data = {
            "status" : AgentStatus.error,
            "text" : str(error),
        }
        self.queue.put_nowait(dumps(data))

    async def on_agent_action(
            self,
            action: AgentAction,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            tags: Optional[List[str]] = None,
            **kwargs: Any,
    ) -> None:
        data = {
            "status" : AgentStatus.agent_action,
            "tool_name" : action.tool,
            "tool_input" : action.tool_input,
            "text": action.log,
        }
        self.queue.put_nowait(dumps(data))

    async def on_agent_finish(
            self, finish: AgentFinish, *, run_id: UUID, parent_run_id: Optional[UUID] = None,
            tags: Optional[List[str]] = None,
            **kwargs: Any,
    ) -> None:
        if "Thought:" in finish.return_values["output"]:
            finish.return_values["output"] = finish.return_values["output"].replace("Thought:", "")

        data = {
            "status" : AgentStatus.agent_finish,
            "text" : finish.return_values["output"],
        }
        self.done.set()
        self.queue.put_nowait(dumps(data))
