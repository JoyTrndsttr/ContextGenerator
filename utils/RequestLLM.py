import requests
import re
import random

class RequestLLM:
    def __init__(self):
        self.config = {
            "max_tokens": 2000,
            "do_sample": True,
            "repetition_penalty": 1.1,
            "temperature": 0,
            "port": 8000
        }

    def request_deepseek(self, user_prompt, system_prompt=None):
        port = 8000
        # port = random.choice([8000,8001])
        url = f"http://localhost:{port}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "model": "/mnt/ssd2/wangke/.cache/deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            "messages": [],
            "max_new_tokens": self.config["max_tokens"],
            "do_sample": self.config["do_sample"],
            "repetition_penalty": self.config["repetition_penalty"],
            "temperature": self.config["temperature"]
        }
        if system_prompt:
            data["messages"] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        else:
            data["messages"] = [{"role": "user", "content": user_prompt}]
        try:
            response = requests.post(url, headers=headers, json=data).json()
            result = response['choices'][0]['message']['content']
            print(result)
            output = result.split("</think>")[1]
            think = result.split("</think>")[0]
            new_code = re.search(r'```(.*)```', output, re.DOTALL)
            if not new_code:
                print("No code found in response 1")
                return None, think, output
            if new_code: 
                new_code = new_code.group(1)
                new_code = new_code.split("\n", 1)[1] #未验证
                if not new_code:
                    print("No code found in response 2")
                return new_code, think, output
        except Exception as e:
            print(e)
            print("No code found in response 3")
            print(user_prompt)
            return None, None, None

def main():
    prompt = "法国的首都是哪里"
    llm = RequestLLM()
    code, think, output = llm.request_deepseek(prompt)
    print(output)

if __name__ == '__main__':
    main()