import requests
from typing import Any, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, ChatMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from config.settings import settings

class CustomOpenAIChatModel(BaseChatModel):
    base_url: str
    api_key: str
    model_name: str
    temperature: float = 0.3

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # 1. Convert LangChain messages to OpenAI format
        formatted_messages = []
        for m in messages:
            role = "user" # Default to user, adjust for system/ai as needed
            if m.type == "ai":
                role = "assistant"
            elif m.type == "system":
                role = "system"
            
            formatted_messages.append({
                "role": role,
                "content": m.content
            })

        # 2. Build the OpenAI-compatible payload
        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": self.temperature,
        }
        if stop:
            payload["stop"] = stop

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 3. Hit the /chat/completions endpoint
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        
        response = requests.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        
        # 4. Parse the OpenAI-style response
        response_data = response.json()
        ai_content = response_data["choices"][0]["message"]["content"]

        # 5. Return LangChain ChatResult
        message = AIMessage(content=ai_content)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "custom_openai_compatible"

# --- Usage Example ---
if __name__ == "__main__":
    from langchain_core.messages import HumanMessage
    
    llm = CustomOpenAIChatModel(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model_name=settings.llm_model_name,
        temperature=settings.llm_temperature
    )

    response = llm.invoke([HumanMessage(content="Say hello and confirm the LLM is working.")])
    print(response.content)
