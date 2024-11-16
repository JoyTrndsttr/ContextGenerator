from typing import Dict, List
from openai import OpenAI

class OpenAIUtils:

    def __init__(self, model_id: str, generation_kwargs):
        self._model_id = model_id
        self._generation_kwargs = generation_kwargs
        self._base_url = "http://202.197.33.222:13003/v1"
        self._api_key = "EMPTY"

    # @backoff.on_exception(backoff.constant, Exception, interval=10)
    def get_completion(self, prompts: List[str]) -> str:
        client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        messages = [
            {"role": "user", "content": prompts[0]},
        ]
        response = client.chat.completions.create(
                model=self._model_id,
                messages=messages,
                **self._generation_kwargs
            )
        # print(response.choices[0].message.content)
        return response.choices[0].message.content

generation_kwargs = {
    "max_tokens": 15,
    "temperature": 0.8,
    "top_p": 0.95,
    "n": 1,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0
    }

# model = OpenAIUtils(model_id="llama:7b", generation_kwargs=generation_kwargs)
# model.get_completion(["What is the capital of France?"])