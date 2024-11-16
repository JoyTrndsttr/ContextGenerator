import requests

url = "http://202.197.33.222:13003/v1/completions"
headers = {
    "Content-Type": "application/json"
}
data = {
    "model": "llama:7b",
    "prompt": "What is the capital of France?",
    "max_tokens": 7,
    "temperature": 0
}

response = requests.post(url, headers=headers, json=data)
print(response.json())