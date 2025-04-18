import json
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import multiprocessing as mp
import time

github_tokens = json.load(open("/home/wangke/model/ContextGenerator/settings.json", encoding='utf-8'))["github_tokens"]
token_index = 0
GITHUB_TOKEN = github_tokens[token_index]
repo_dir = "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/success_repos.json"
output_dir = "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_repo_datasets.json"
dataset_id = 0

def update_github_token():
    global GITHUB_TOKEN
    global token_index
    token_index = (token_index + 1) % len(github_tokens)
    GITHUB_TOKEN = github_tokens[token_index]

def get_datasample(diff, review, repo, commit_url):
    global dataset_id
    dataset_id += 1
    diff_lines = diff.split("\n")
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
        "_id": dataset_id,
        "repo": repo,
        "old": '\n'.join(old_lines),
        "new": '\n'.join(new_lines),
        "review": review,
        "language": "py",
        "commit_url": commit_url,
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

def get_content(url):
    try:
        global GITHUB_TOKEN
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        response = requests_retry_session().get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting {url}: {e}")
        time.sleep(60)
        GITHUB_TOKEN = json.load(open("/home/wangke/model/ContextGenerator/settings.json", encoding='utf-8'))["GITHUB_TOKEN"]
        get_content(url)

def get_pulls(repo):
    print(f"processing repo {repo}")
    #分页处理过多的pulls
    i=0
    while(True):
        pulls = get_content(f"https://api.github.com/repos/{repo}/pulls?state=all&page={i+1}")
        if not pulls: break
        i += 1
        datasets = []
        for pull in pulls:
            # pull = get_content(f"https://api.github.com/repos/{repo}/pulls/4436")
            print(f"processing pull {pull['number']}")
            if pull["created_at"] < "2023-03-01T00:00:00Z": break
            #获取commit信息
            commits_url = pull["commits_url"]
            commits = get_content(commits_url)

            #获取review信息
            comments_url = pull["review_comments_url"]
            comments = get_content(comments_url)
            for comment in comments:
                if comment["diff_hunk"]:
                    # print(comment["diff_hunk"])
                    comment_created_time = comment["created_at"]
                    # 找到diff_hunk中以'+'和'-'开头的行
                    path = comment["path"]
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
                        commit = get_content(url)
                        files = commit["files"]
                        #file过多时，需要分页处理
                        page = 1
                        while True:
                            page += 1
                            commit_next_page_url = f"{url}?page={page}"
                            commit_next_page = get_content(commit_next_page_url)
                            if not commit_next_page["files"]: break
                            files.extend(commit_next_page["files"])
                        for file in files:
                            file_path = file["filename"]
                            if file_path != path: continue
                            patch = file.get("patch", None)
                            if not patch: break
                            hunks = patch.split("@@")
                            #去除只包含一行的hunk（即不包含\n）
                            hunks = [hunk for hunk in hunks if hunk.count("\n") > 0]
                        
                        if not hunks: continue
                        for hunk in hunks:
                            hunk_lines = hunk.split('\n')
                            hunk_lines = [line[1:].strip() for line in hunk_lines]   
                            if len(hunk_lines) > 20: continue
                            #如果lines的每一行都在hunk中，则匹配成功
                            if all(line in hunk_lines for line in lines):
                                match_flag = True
                                # datasets.append(datasets)
                                dataset = get_datasample(hunk, comment["body"], repo, f"http://github.com/{repo}/pull/{pull['number']}/commits/{commit['sha']}")
                                #将这一条记录添加到datasets中
                                with open(f"{output_dir}", "a", encoding='utf-8') as f:
                                    json.dump(dataset, f, ensure_ascii=False)
                                    f.write("\n")
                                break
                        if match_flag: break
                else : print(f"no diff_hunk in {comment['id']}")

def process_dataset(repo):
    try:
        get_pulls(repo)
    except Exception as e:
        print(f"Error processing {repo}: {e}")

def main():
    _dublicate_repos = []
    repos = []
    last_processed_id = 0
    # with open(output_dir, "r") as f0:
    #     for line in f0:
    #         dataset = json.loads(line.strip())
    #         repo = dataset['repo']
    #         if repo not in _dublicate_repos:
    #             _dublicate_repos.append(repo)
    #         last_processed_id = dataset['_id']
    global dataset_id
    dataset_id = last_processed_id
    with open(repo_dir, "r") as f:
        repos = [line.strip() for line in f]
        print(f"待处理的repo数量：{len(repos)}")
    # with open('/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_llama.json', 'r') as f:
    #     records = json.load(f)
    #     for record in records:
    #         repo = record['repo']
    #         if repo not in repos and repo not in _dublicate_repos:
    #             repos.append(repo)
    # 多进程处理
    # with mp.Pool(processes=10) as pool:
    #     pool.starmap(get_pulls, [(repo,) for repo in repos])
    # with mp.Pool(processes=5) as pool:
    #     results = [pool.apply_async(process_dataset, (repo,)) for repo in repos]
    #     pool.close()
    #     pool.join()
    for repo in repos:
        process_dataset(repo)
        
    # get_pulls()

if __name__ == '__main__':
    main()