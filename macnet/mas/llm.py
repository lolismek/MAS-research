import os

from typing import (
    Protocol, 
    Literal,  
    Optional, 
    List,
)
from openai import OpenAI
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .utils import load_config


# model configs
CONFIG: dict = load_config("configs/configs.yaml")
LLM_CONFIG: dict = CONFIG.get("llm_config", {})
MAX_TOKEN = LLM_CONFIG.get("max_token", 8192)
TEMPERATURE = LLM_CONFIG.get("temperature", 0.1)
NUM_COMPS = LLM_CONFIG.get("num_comps", 1)

# Route through the local OpenAI-compatible proxy's Tinker/Qwen3.6 backend (/m/<tag>/v1).
# MACNET_TAG makes every call attributable in shared/proxy/{calls,raw_calls}.jsonl; the proxy
# strips <think>...</think> from the reply and logs it under `reasoning` in raw_calls.jsonl.
PROXY = os.environ.get("PROXY_URL", "http://127.0.0.1:8744/v1")
TAG = os.environ.get("MACNET_TAG", "macnet_dev")
_base, _v1 = PROXY.rsplit("/", 1)
URL = f"{_base}/m/{TAG}/{_v1}"
KEY = "dummy"
print('# api url: ', URL)


completion_tokens, prompt_tokens = 0, 0

@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant"]
    content: str

class LLMCallable(Protocol):

    def __call__(
        self,
        messages: List[Message],
        temperature: float = TEMPERATURE,
        max_tokens: int = MAX_TOKEN,
        stop_strs: Optional[List[str]] = None,
        num_comps: int = NUM_COMPS
    ) -> str:
        pass

class LLM(ABC):
    
    def __init__(self, model_name: str):
        self.model_name: str = model_name

    @abstractmethod
    def __call__(
        self,
        messages: List[Message],
        temperature: float = TEMPERATURE,
        max_tokens: int = MAX_TOKEN,
        stop_strs: Optional[List[str]] = None,
        num_comps: int = NUM_COMPS
    ) -> str:
        pass

class GPTChat(LLM):

    def __init__(self, model_name: str):
        super().__init__(model_name=model_name)
        self.client = OpenAI(
            base_url=URL,
            api_key=KEY
        )

    def __call__(
        self,
        messages: List[Message],
        temperature: float = TEMPERATURE,
        max_tokens: int = MAX_TOKEN,
        stop_strs: Optional[List[str]] = None,
        num_comps: int = NUM_COMPS
    ) -> str:
        import time
        global prompt_tokens, completion_tokens
        
        messages = [{"role": msg.role, "content": msg.content} for msg in messages]

        max_retries = 5  
        wait_time = 1 

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=min(max_tokens or 28000, 28000),
                    temperature=temperature,
                    n=num_comps or 1,
                    # NOTE: `stop` intentionally omitted. MacNet/DyLAN set stop=['\n'], but Qwen3.6
                    # prefills <think> and reasons first, so stop=['\n'] would halt inside the think
                    # block -> no </think> -> the proxy returns a CoT fragment as the "answer".
                    # The envs' process_action() already takes the first line of the reply.
                )

                answer = response.choices[0].message.content
                prompt_tokens += response.usage.prompt_tokens
                completion_tokens += response.usage.completion_tokens
                
                if answer is None:
                    print("Error: LLM returned None")
                    continue
                return answer  

            except Exception as e:
                error_message = str(e)
                if "rate limit" in error_message.lower() or "429" in error_message:
                    time.sleep(wait_time)
                else:
                    print(f"Error during API call: {error_message}")
                    break 

        return "" 


def get_price():
    global completion_tokens, prompt_tokens
    return completion_tokens, prompt_tokens, completion_tokens*60/1000000+prompt_tokens*30/1000000
