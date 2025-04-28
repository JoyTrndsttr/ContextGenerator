import json
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import time
from datetime import datetime, timezone, timedelta

class RequestGitHub:
    def __init__(self):
        self.github_tokens = json.load(open("/home/wangke/model/ContextGenerator/settings.json", encoding='utf-8'))["github_tokens"]
        self.valid_github_tokens = [token for token in self.github_tokens if self.check_github_rate_limit(token)]
        self.token_index = 0

    def check_github_rate_limit(self, token):
        url = "https://api.github.com/rate_limit"
        headers = {'Authorization': f'token {token}'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            remaining = data["rate"]["remaining"]
            reset_time = data["rate"]["reset"]  # Unix 时间戳
            utc_time = datetime.fromtimestamp(reset_time, timezone.utc)
            china_time = utc_time.astimezone(timezone(timedelta(hours=8)))
            time = china_time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"GitHub API '{token}'")
            print(f"剩余请求次数: {remaining}; API 限制重置时间 (UTC): {time}")
            return True
        else:
            print(f"GitHub API '{token}'请求失败，状态码: {response.status_code}")
            return False
    
    def next_github_token(self):
        self.token_index = (self.token_index + 1) % len(self.github_tokens)
        return self.github_tokens[self.token_index]