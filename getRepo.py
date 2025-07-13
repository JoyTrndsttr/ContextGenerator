import json
import requests
from requests.adapters import HTTPAdapter
import time
import json
import os
import subprocess
from utils.RequestGitHub import RequestGitHub

# 加载GitHub访问令牌
requestGitHub = RequestGitHub()
clone_dir = r'/data/DataLACP/wangke/recorebench/repo/repo'

java_config = {
    "source_dir" : "/mnt/ssd2/wangke/CR_data/dataset/pre/cacr_java.json",
    "output_dir" : "/data/DataLACP/wangke/recorebench/java/process/repos_java.json",
    "success_repo_dir" : "/data/DataLACP/wangke/recorebench/java/process/success_repos_2_java.json",
    "failed_repo_dir" : "/data/DataLACP/wangke/recorebench/java/process/failed_repos_2_java.json"
}
js_config = {
    "source_dir" : "/mnt/ssd2/wangke/CR_data/dataset/pre/cacr_js.json",
    "output_dir" : "/data/DataLACP/wangke/recorebench/js/process/repos_js.json",
    "success_repo_dir" : "/data/DataLACP/wangke/recorebench/js/process/success_repos_2_js.json",
    "failed_repo_dir" : "/data/DataLACP/wangke/recorebench/js/process/failed_repos_2_js.json"
}

config = js_config
source_dir = config["source_dir"]
output_dir = config["output_dir"]
success_repo_dir = config["success_repo_dir"]
failed_repo_dir = config["failed_repo_dir"]

def get_top_repos(top_n=5000, language="java"):
    url = "https://api.github.com/search/repositories"
    query_params = {
        "q": f"language:{language}",
        "sort": "stars",
        "order": "desc",
        "per_page": 100
    }
    repos = []
    while len(repos) < top_n:
        response = requestGitHub.get_response(url, params=query_params)
        data, links = response.json(), response.links
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

def get_pull_request_count(repo):
    url = f"https://api.github.com/repos/{repo}/pulls?state=all&per_page=1"
    response = requestGitHub.get_response(url)
    if response.status_code == 200:
        pr_count = int(response.headers.get('link', '').split(",")[1].split("page=")[2].split(">")[0]) if 'link' in response.headers else 0
        return pr_count
    return 0

def get_repo_size(repo):
    url = f"https://api.github.com/repos/{repo}"
    response = requestGitHub.get_response(url)
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
    try:
        with open(output_dir, 'r') as f:
            dublicate_repos = json.load(f)
    except:
        dublicate_repos = []
    # Load the repositories from the JSON file
    try:
        with open(source_dir, 'r') as f:
            records = json.load(f)
            repos = list(set([record['repo'] for record in records]))
    except:
        repos = []
    # Load the repositories from the Failed JSON file
    try:
        with open(failed_repo_dir, 'r') as f:
            failed_repos = json.load(f)
    except:
        failed_repos = []
    
    # repos = list(set(repos) - set(dublicate_repos))
    repos = list(set(dublicate_repos + repos + failed_repos))
    new_repos = get_top_repos(top_n=5000, language="js")
    repos = list(set(repos + new_repos))
    with open(output_dir, "w") as f:
        json.dump(repos+dublicate_repos, f)
    print(f"Repositories to process: {len(repos)}")
    
    clone_count = 0
    for repo in repos:
        if os.path.exists(os.path.join(clone_dir, repo.split('/')[-1])):
            continue

        try:
            pr_count = get_pull_request_count(repo)
            if pr_count <= 50:
                continue

            repo_size = get_repo_size(repo)
            if repo_size > 614400:  # More than 600MB in KB
                continue
        except Exception as e:
            print(f"Error getting pull request count or repo size for {repo}: {e}")
            with open(failed_repo_dir, "a") as f:
                f.write(f"{repo}\n")
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
