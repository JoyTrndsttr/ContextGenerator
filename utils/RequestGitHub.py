import json
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import time
from datetime import datetime, timezone, timedelta
import traceback

class RequestGitHub:
    def __init__(self):
        self.github_tokens = json.load(open("/home/wangke/model/ContextGenerator/settings.json", encoding='utf-8'))["github_tokens"]
        # self.valid_github_tokens = [token for token in self.github_tokens if self.check_github_rate_limit(token)]
        self.valid_github_tokens = self.github_tokens
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
    
    def requests_retry_session(
        self,
        retries=5,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 504),
        session=None,
    ):
        session = session or requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def get_response(self, url):
        for j in range(6):
            for i in range(len(self.valid_github_tokens)):
                try:
                    headers = {'Authorization': f'token {self.next_github_token()}'}
                    response = self.requests_retry_session().get(url, headers=headers, timeout=10)
                    response.raise_for_status()
                    return response
                except Exception as e:
                    print(f"Error getting {url}: {e}")
                    try:
                        if e.response.status_code == 403: continue
                    except:
                        pass
                    else: 
                        traceback.print_exc()
                        # raise Exception(f"{e.response.status_code}")
            time.sleep(600)
        raise Exception(f"url forbidden after 6 retries")
    
    #用于response.json()返回的是一个list，但是分成多页的情况
    def get_response_and_merge_list_pages_aware(self, url):
        results = []
        for page in range(1, 100):
            for j in range(6):
                flag = False
                for i in range(len(self.valid_github_tokens)):
                    try:
                        headers = {'Authorization': f'token {self.next_github_token()}'}
                        response = self.requests_retry_session().get(f"{url}?page={page}", headers=headers, timeout=10)
                        response.raise_for_status()
                        if response:
                            for item in response.json():
                                results.append(item)
                            flag = True
                            break
                        else:
                            flag = True
                            break
                    except Exception as e:
                        print(f"Error getting {url}: {e}")
                        if e.response.status_code == 403: continue
                        else: 
                            traceback.print_exc()
                            raise Exception(f"{e.response.status_code}")
                time.sleep(600)
            raise Exception(f"url forbidden after 6 retries")
        return results
    
    #用于response.json()返回的是一个list，但是一页一页查询
    def get_response_by_page(self, url, page):
        for j in range(6):
            for i in range(len(self.valid_github_tokens)):
                try:
                    headers = {'Authorization': f'token {self.next_github_token()}'}
                    response = self.requests_retry_session().get(f"{url}?page={page}", headers=headers, timeout=10)
                    response.raise_for_status()
                    return response
                except Exception as e:
                    print(f"Error getting {url}: {e}")
                    if e.response.status_code == 403: continue
                    else: 
                        traceback.print_exc()
                        raise Exception(f"{e.response.status_code}")
            time.sleep(600)
        raise Exception(f"url forbidden after 6 retries")

    def get_full_content(self, url):
        result = []
        response = self.get_response(url)
        link_header = response.headers.get('Link')
        result.append(response.json())
        while link_header:
            if link_header.split('page=')[1].split('>')[0] == '1' : break
            url = link_header.split('<')[1].split('>')[0]
            response = self.get_response(url)
            link_header = response.headers.get('Link')
            result.append(response.json())
        return result