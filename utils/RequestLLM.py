import requests
import re
import random

class RequestLLM:
    def init():
        pass

    def request_deepseek(self, prompt, config={
        "max_tokens": 2000,
        "do_sample": True,
        "repetition_penalty": 1.1,
        "temperature": 0,
        "port": 8000
    }):
        port = 8000
        # port = random.choice([8000,8001])
        url = f"http://localhost:{port}/v1/chat/completions"
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
            "max_new_tokens": config["max_tokens"],
            "do_sample": config["do_sample"],
            "repetition_penalty": config["repetition_penalty"],
            "temperature": config["temperature"]
        }
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
            # if not new_code:
            #     old_lines = old.split("\n")
            #     start = old_lines[0]
            #     end = old_lines[-1]
                # new_code = process(output, start, end)
            if new_code: 
                new_code = new_code.group(1)
                # if new_code.startswith("python"):
                #     new_code = new_code[6:]
                new_code = new_code.split("\n", 1)[1] #未验证
                if not new_code:
                    print("No code found in response 2")
                return new_code, think, output
        except Exception as e:
            print(e)
            print("No code found in response 3")
            print(prompt)
            return None, None, None

def main():
    prompt = "法国的首都是哪里"
    llm = RequestLLM()
    code, think, output = llm.request_deepseek(prompt)
    print(output)

if __name__ == '__main__':
    main()