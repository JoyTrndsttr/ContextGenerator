from openai import OpenAI
import re

class OpenAIUtils:
    def __init__(self, model_id):
        self._model_id = model_id
        self._generation_kwargs = {
            "max_tokens": 1000,
            "temperature": 0,
            "top_p": 0.95,
            "n": 1,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0
        }
        self._base_url = "http://202.197.33.222:13003/v1"
        self._api_key = "EMPTY"

    def get_completion(self, user_prompt, system_prompt = None) -> str:
        client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        else:
            messages = [{"role": "user", "content": user_prompt}]
        response = client.chat.completions.create(
                model=self._model_id,
                messages=messages,
                **self._generation_kwargs
            )
        return response.choices[0].message.content

def get_model_response(model, user_prompt, system_prompt = None):
    answer = model.get_completion(user_prompt, system_prompt if system_prompt else None)
    result = re.search(r'```(.*)```', answer,re.DOTALL)
    print(f"prompt:\n{user_prompt}\nanswer:\n{answer}")
    if result:
        newcode = result.group(1)
    return newcode if result else "", answer

def main():
    model_id = "llama:7b"
    user_prompt = "What is the weather today?"
    print(get_model_response(OpenAIUtils(model_id), user_prompt))

if __name__ == '__main__':
    main()