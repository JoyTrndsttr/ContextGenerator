import json
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import time
import json
import os
import subprocess

# 加载GitHub访问令牌
github_tokens = json.load(open("/home/wangke/model/ContextGenerator/settings.json", encoding='utf-8'))["github_tokens"]
token_index = 0
GITHUB_TOKEN = github_tokens[token_index]
clone_dir = r'/mnt/ssd2/wangke/CR_data/repo'
output_dir = "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/repos.json"
success_repo_dir = "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/success_repos_2.json"
failed_repo_dir = "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/failed_repos_2.json"

def update_github_token():
    global GITHUB_TOKEN
    global token_index
    token_index = (token_index + 1) % len(github_tokens)
    GITHUB_TOKEN = github_tokens[token_index]

def fetch_data(url, params, session):
    """ 使用给定的session发送请求，如果请求失败，则更换token重试 """
    while True:
        try:
            response = session.get(url, params=params)
            response.raise_for_status()
            return response.json(), response.links
        except requests.exceptions.HTTPError as e:
            if response.status_code == 403 or response.status_code == 422:  # API限额或参数问题
                update_github_token()
                session.headers.update({"Authorization": f"token {GITHUB_TOKEN}"})
                time.sleep(1)  # 等待一秒再重试
            else:
                raise e

def get_top_repos(top_n=5000, language="python"):
    url = "https://api.github.com/search/repositories"
    query_params = {
        "q": f"language:{language}",
        "sort": "stars",
        "order": "desc",
        "per_page": 100
    }
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # 设置重试策略
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session = requests.Session()
    session.mount('https://', adapter)
    session.headers.update(headers)

    repos = []
    while len(repos) < top_n:
        data, links = fetch_data(url, query_params, session)
        for item in data["items"]:
            repo_name = f"{item['owner']['login']}/{item['name']}"
            repos.append(repo_name)
            if len(repos) >= top_n:
                return repos
        # 更新请求的下一页链接
        if 'next' in links:
            url = links['next']['url']
            query_params = None  # 下一次请求URL已包含必要的参数
        else:
            break

    return repos

def requests_retry_session(retries=5, backoff_factor=0.3, status_forcelist=(500, 502, 504), session=None):
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

def get_pull_request_count(repo):
    url = f"https://api.github.com/repos/{repo}/pulls?state=all&per_page=1"
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests_retry_session().get(url, headers=headers)
    if response.status_code == 200:
        pr_count = int(response.headers.get('link', '').split(",")[1].split("page=")[2].split(">")[0]) if 'link' in response.headers else 0
        return pr_count
    return 0

def get_repo_size(repo):
    url = f"https://api.github.com/repos/{repo}"
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests_retry_session().get(url, headers=headers)
    if response.status_code == 200:
        size = response.json().get('size', 0)  # Size is in KB
        return size
    return 0

def clone_repository(repo_url, full_clone_path):
    max_attempts = 1
    for attempt in range(max_attempts):
        try:
            subprocess.run(['git', 'clone', repo_url, full_clone_path], check=True)
            print(f"Successfully cloned {repo_url} into {full_clone_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Attempt {attempt + 1} failed for {repo_url}: {e}")
            time.sleep(5)
    return False

def process_repositories():
    # Load the repositories from the JSON file
    with open(output_dir, 'r') as f:
        repos = json.load(f)
    
    new_repos = get_top_repos(top_n=5000, language="java")
    repos = list(set(repos + new_repos))
    with open(output_dir, "w") as f:
        json.dump(repos, f)
    
    clone_count = 0
    for repo in repos:
        if os.path.exists(os.path.join(clone_dir, repo.split('/')[-1])):
            continue

        pr_count = get_pull_request_count(repo)
        if pr_count <= 50:
            continue

        repo_size = get_repo_size(repo)
        if repo_size > 51200:  # More than 50MB in KB
            continue

        repo_url = f"https://githubfast.com/{repo}.git"
        full_clone_path = os.path.join(clone_dir, repo.split('/')[-1])
        if clone_repository(repo_url, full_clone_path):
            clone_count += 1
            with open(success_repo_dir, "a") as f:
                f.write(f"{repo}\n")
        else:
            with open(failed_repo_dir, "a") as f:
                f.write(f"{repo}\n")

    print(f"Total repositories cloned: {clone_count}")

if __name__ == "__main__":
    # top_repos = get_top_python_repos()
    # for repo in top_repos:
    #     print(repo)
    # with open(output_dir, "w") as f:
    #     json.dump(top_repos, f)
    process_repositories()
