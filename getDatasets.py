import json
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from utils.RequestGitHub import RequestGitHub
import multiprocessing as mp
from multiprocessing import Value, Lock
import time
import os
import traceback
import re

# 用来控制获取的GitHub token
requestGitHub = RequestGitHub()


java_config = {
    "lang": "java",
    "repo_dir1": "/data/DataLACP/wangke/recorebench/java/process/success_repos_2_java.json",
    "output_dir": "/data/DataLACP/wangke/recorebench/java/datasets/new_datasets_java.json",
    "log_dir": "/data/DataLACP/wangke/recorebench/java/log/getDatasets.txt",
}
js_config = {
    "lang": "js",
    "repo_dir1": "/data/DataLACP/wangke/recorebench/js/process/success_repos_2_js.json",
    "output_dir": "/data/DataLACP/wangke/recorebench/js/datasets/new_datasets_js.json",
    "log_dir": "/data/DataLACP/wangke/recorebench/js/log/getDatasets.txt",
}

config = js_config

lang = config["lang"]
repo_dir1 = config["repo_dir1"]
output_dir = config["output_dir"]
log_dir = config["log_dir"]
dataset_id = Value('i', 0)
dataset_lock = Lock()

def get_datasample(diff, review, repo, commit_url, review_url, comment_info):
    with dataset_lock:  # 加锁，确保只有一个进程能访问
        dataset_id.value += 1
        assigned_id = dataset_id.value
    diff_lines = diff.split("\n")[1:]
    old_lines = []
    new_lines = []
    for line in diff_lines:
        if line.startswith("-"):
            old_lines.append(line)
        elif line.startswith("+"):
            new_lines.append(line)
        else:
            old_lines.append(line)
            new_lines.append(line)
    return {
        "_id": assigned_id,
        "repo": repo,
        "old": '\n'.join(old_lines),
        "new": '\n'.join(new_lines),
        "diff_hunk": diff,
        "review": review,
        "language": lang,
        "commit_url": commit_url,
        "review_url": review_url,
        "comment": comment_info
    }

def requests_retry_session(
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

def get_content(url, token):
    for i in range(6):
        try:
            headers = {'Authorization': f'token {token}'}
            response = requests_retry_session().get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting {url}: {e}")
            traceback.print_exc()
            time.sleep(600)
    raise Exception(f"Failed to get {url} after 6 retries")

def get_pulls(repo, pull_id = 1000000):
    print(f"processing repo {repo}")
    #分页处理过多的pulls
    i=0
    while(True):
        pulls = requestGitHub.get_response(f"https://api.github.com/repos/{repo}/pulls?state=all&page={i+1}").json()
        if not pulls: break
        i += 1
        for pull in pulls:
            if pull["number"] > pull_id: continue
            try:
                print(f"processing repo {repo} pull {pull['number']}")
                # if pull["created_at"] < "2023-03-01T00:00:00Z": break
                created_at = pull["created_at"]
                #获取commit信息
                commits_url = pull["commits_url"]
                commits = requestGitHub.get_response(commits_url).json()

                #获取review信息
                comments_url = pull["review_comments_url"]
                comments = requestGitHub.get_response(comments_url).json()

                for comment in comments:
                    if comment["diff_hunk"]:
                        comment_created_time = comment["created_at"]
                        # 找到diff_hunk中以'+'和'-'开头的行
                        path = comment["path"]
                        if not path.endswith(f".{lang}"): continue
                        comment_info = {
                            "diff_hunk": comment["diff_hunk"],
                            "review_position_line": comment["diff_hunk"].split('\n')[-1][1:], #一般来说最后一行是review指向的行
                        }
                        review_url = comment["url"]
                        diff_hunk = comment["diff_hunk"]
                        diff_hunk = diff_hunk.split("@@")[-1]
                        diff_hunk_lines = diff_hunk.split("\n")
                        if len(diff_hunk_lines) > 20: continue
                        lines = []
                        for line in diff_hunk_lines:
                            if line.startswith("+"):
                                lines.append(line)
                        if not lines:
                            print(f"no changed line in {comment['id']}")
                            continue
                        lines = [line[1:].strip() for line in lines]

                        for commit in commits:
                            hunks = []
                            match_flag = False
                            commit_time = commit["commit"]["committer"]["date"]
                            if comment_created_time >= commit_time: continue
                            #找commit after comment
                            url = commit["url"]
                            commit = requestGitHub.get_response(url).json()
                            files = commit["files"]
                            #file过多时，需要分页处理
                            page = 1
                            while True:
                                page += 1
                                commit_next_page_url = f"{url}?page={page}"
                                commit_next_page = requestGitHub.get_response(commit_next_page_url).json()
                                if not commit_next_page["files"]: break
                                files.extend(commit_next_page["files"])
                            for file in files:
                                file_path = file["filename"]
                                if file_path != path: continue
                                patch = file.get("patch", None)
                                if not patch: break
                                hunk = []
                                for line in patch.split('\n'):
                                    if line.startswith("@@"):
                                        if hunk: hunks.append('\n'.join(hunk))
                                        hunk = []
                                    hunk.append(line)
                                if hunk: hunks.append('\n'.join(hunk))
                            if not hunks: continue
                            for hunk in hunks:
                                hunk_lines = hunk.split('\n')
                                # 取RevisionDiffHunk中的old code，去掉开头的'+'/ '-'/ ' '
                                hunk_lines = [line[1:].strip() for line in hunk_lines if not line.startswith('+')]   
                                if len(hunk_lines) > 20: continue
                                #如果lines的每一行都在hunk中，则匹配成功
                                if all(line in hunk_lines for line in lines):
                                    match_flag = True
                                    # datasets.append(datasets)
                                    dataset = get_datasample(hunk, comment["body"], repo, f"http://github.com/{repo}/pull/{pull['number']}/commits/{commit['sha']}", review_url, comment_info)
                                    dataset["created_at"] = created_at
                                    #将这一条记录添加到datasets中
                                    with open(f"{output_dir}", "a", encoding='utf-8') as f:
                                        json.dump(dataset, f, ensure_ascii=False)
                                        f.write("\n")
                                        print(f"add dataset {dataset['_id']}")
                                    break
                            if match_flag: break
                    else : print(f"no diff_hunk in {comment['id']}")
            except Exception as e:
                print(f"Error processing {repo} pull {pull['number']}: {e}")
                traceback.print_exc()
                continue

def process_dataset(repo, id=1000000):
    try:
        get_pulls(repo, id)
    except Exception as e:
        print(f"Error processing {repo}: {e}")
        traceback.print_exc()

def extract_last_pulls(log_dir):
    pattern = re.compile(r'processing repo (\S+) pull (\d+)')
    repo_latest = {}

    with open(log_dir, 'r', encoding='utf-8') as log_file:
        for line in log_file:
            match = pattern.search(line)
            if match:
                repo = match.group(1)
                pull_id = int(match.group(2))
                if repo not in repo_latest or pull_id < repo_latest[repo]:
                    repo_latest[repo] = pull_id

    return repo_latest

def main():
    _dublicate_repos = []
    repos = []
    # dataset_id.value = 9404
    # with open('/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_llama.json', 'r') as f:
    #     records = json.load(f)
    #     for record in records:
    #         repo = record['repo']
    #         if repo not in repos and repo not in _dublicate_repos:
    #             repos.append(repo)
    with open(repo_dir1, "r") as f1:
        _repos = [line.strip() for line in f1]
        for repo in _repos:
            if repo not in repos and repo not in _dublicate_repos:
                repos.append(repo)
    # with open(repo_dir2, "r") as f2:
    #     _repos = [line.strip() for line in f2]
    #     for repo in _repos:
    #         if repo not in repos and repo not in _dublicate_repos:
    #             repos.append(repo)
    print(f"待处理的repo数量：{len(repos)}")

    try:
        repo_latest = extract_last_pulls(log_dir)
    except:
        repo_latest = {}

    pairs = []
    
    for repo in repos:
        if repo in repo_latest:
            id = repo_latest[repo]
            if id > 100:
                pairs.append((repo, id))
        else:
            pairs.append((repo, 1000000))
    
    with mp.Pool(14) as pool:
        results = [pool.apply_async(process_dataset, (repo, id)) for repo, id in pairs]
        pool.close()
        pool.join()

if __name__ == '__main__':
    main()