import requests
import re

class RequestLLM:
    def init():
        pass

    def request_deepseek(self, prompt, old):
        url = "http://localhost:8000/v1/chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "model": "/mnt/ssd2/wangke/.cache/deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            "messages": [
                                {
                                        "role": "user",
                                        "content": prompt
                                }
                        ],
            "max_new_tokens": 3000,
            "do_sample": False,
            "temperature": 0
        }

        response = requests.post(url, headers=headers, json=data).json()
        result = response['choices'][0]['message']['content']
        print(result)
        try:
            output = result.split("</think>")[1]
            new_code = re.search(r'```(.*)```', output, re.DOTALL)
            if not new_code:
                print("No code found in response 1")
            # if not new_code:
            #     old_lines = old.split("\n")
            #     start = old_lines[0]
            #     end = old_lines[-1]
                # new_code = process(output, start, end)
            if new_code: 
                new_code = new_code.group(1)
                if new_code.startswith("python"):
                    new_code = new_code[6:]
                if not new_code:
                    print("No code found in response 2")
                return new_code
        except Exception as e:
            print(e)
            print("No code found in response 3")
            return None
