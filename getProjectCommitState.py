import psycopg2
from psycopg2 import sql
import subprocess
import requests
import os
import json
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry # type: ignore
import re

# GitHub 个人访问令牌
# GITHUB_TOKEN = json.load(open("settings.json", encoding='utf-8'))["GITHUB_TOKEN"]
GITHUB_TOKEN = json.load(open("/home/wangke/model/ContextGenerator/settings.json", encoding='utf-8'))["github_tokens"][0]

# 最大查找 parent commit 的次数
MAX_PARENT_SEARCH = 100

# 创建一个带有重试机制的 requests 会话
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

#获取Json文件中的信息
def get_info_from_jsonfile(file_path, id):
    with open(file_path, 'r', encoding='utf-8') as file:
        records = json.load(file)
        for record in records:
            if record['_id'] == id:
                return record

# 使用 GitHub API 获取 commit 信息
def get_commit_info(repo, commit_sha):
    def get_commit_info_by_page(url):
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        response = requests_retry_session().get(url, headers=headers, timeout=10)
        response.raise_for_status()
        link_header = response.headers.get('Link', None)
        commit_info = response.json()
        return link_header,commit_info
    
    url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
    # url = "https://api.github.com/repos/spotify/luigi/commits/03f712cffab169e7b617425c22eb84d82c8f081c"
    
    link_header,commit_infos = get_commit_info_by_page(url)
    while link_header:
        if link_header.split('page=')[1].split('>')[0] == '1' : break
        url = link_header.split('<')[1].split('>')[0]
        link_header,commit_info = get_commit_info_by_page(url)
        commit_infos['files'].extend(commit_info['files'])
    return commit_infos

# 使用 GitHub API 获取评论信息
def get_comment_info(repo, pull, review):
    def normalize_text(text):
        text = re.sub(r'\W+','', text)
        return text

    review_url = f"https://api.github.com/repos/{repo}/pulls/{pull}/comments"
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests_retry_session().get(review_url, headers=headers, timeout=10)
    response.raise_for_status()
    comments = response.json()
    for comment in comments:
        if normalize_text(comment['body']) == normalize_text(review):
            return comment,comment['url']

def get_comment(review_url):
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests_retry_session().get(review_url, headers=headers, timeout=10)
    response.raise_for_status()
    comment = response.json()
    return comment

# 应用文件的补丁
def apply_patch(repo_path, file_info):
    file_path = os.path.join(repo_path, file_info['filename'])
    status = file_info['status']

    def mkDir():
        dir_name = os.path.dirname(file_path)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
    def touchFile():
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write('')
    def delFile():
        if os.path.exists(file_path):
            os.remove(file_path)
    def patchApply():
        if not 'patch' in file_info:
            return
        patch = file_info['patch']
        #TODO: patch也有分页问题，需要根据commit的api查询url，加上```?page=2````参数处理
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.readlines()
        except Exception as e:
            print(f"Error processing patch for {file_path}: {e}")
            return
        start_line = None
        line_change = 0 #补丁所在行修正
        for line in patch.split('\n'):# 解析补丁并应用到文件
            if line.startswith('@@'):
                start_line = int(line.split()[1].split(',')[0][1:]) - 2 + line_change
                if start_line == -2 : start_line = -1 #修正@@号初始值为0带来的影响
            elif line.startswith('+') and start_line is not None:
                file_content.insert(start_line, line[1:] + '\n')
                line_change += 1
            elif line.startswith('-') and start_line is not None:
                if start_line < len(file_content):
                    del file_content[start_line]
                    line_change -= 1
                    start_line -= 1
                else:
                    print(f"Warning: Trying to delete line {start_line} which is out of range in {file_path}")
            start_line += 1
        with open(file_path, 'w', encoding='utf-8') as file:
            file.writelines(file_content)

    if status == 'renamed' :
        pre_file_path = os.path.join(repo_path, file_info['previous_filename'])
        mkDir()
        delFile() #防止开发者采用覆盖的方式移动文件
        os.rename(pre_file_path, file_path)
        patchApply()
    elif status == 'added' :
        mkDir()
        touchFile()
        patchApply()
    elif status == 'deleted' :
        delFile()
    else:
        patchApply()


#获取commit信息
def get_commit_details(repo, commit_url):
    commit_sha = commit_url.split('/')[-1]
    commit_info = get_commit_info(repo, commit_sha)
    files = commit_info.get('files', [])

    paths = []
    code_diff = {}
    
    for file_info in files:
        paths.append(file_info['filename'])
        if 'patch' in file_info:
            code_diff[file_info['filename']] =  file_info['patch']
        else:
            code_diff[file_info['filename']] =  ''

    paths_str = '\n'.join(paths)
    code_diff_str = json.dumps(code_diff)
    return paths_str, code_diff_str

# 还原到特定 commit
def restore_to_commit(repo, repo_path, target_commit):
    current_commit = target_commit
    search_count = 0
    successful_checkout = False
    applied_commits = []

    while search_count < MAX_PARENT_SEARCH:
        try:
            subprocess.run(["git", "checkout", current_commit, "-f"], cwd=repo_path, check=True)
            print(f"Successfully checked out to commit {current_commit} after {search_count} searches")
            subprocess.run(["git", "clean", "-fdx"], cwd=repo_path, check=True)
            print(f"Untracked files and dirs cleaned")
            # subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=repo_path, check=True)
            # print(f"Submodule updated")
            successful_checkout = True
            break
        except subprocess.CalledProcessError:
            print(f"git checkout {current_commit} failed. Fetching parent commit.")
            commit_info = get_commit_info(repo, current_commit)
            parents = commit_info.get('parents', [])
            if not parents:
                print(f"No parent commits found for {current_commit}. Exiting.")
                break
            applied_commits.append(commit_info)
            current_commit = parents[0]['sha']
            search_count += 1

    return successful_checkout, applied_commits

def generate_path_code_diff_to_jsonfile(id , file_path):
    processed_count = 0
    success_count = 0
    failure_count = 0
    successful_checkout = False
    
    record = get_info_from_jsonfile(file_path, id)
    if record:
        record_id, repo, commit_url, review = record["_id"], record["repo"], record["commit_url"], record["review"]
        # print(f"Processing record {record_id} in {file_path}")
        repo_path = f"/mnt/ssd2/wangke/CR_data/repo/{repo.split('/')[1]}"
        commit_hash = commit_url.split('/')[-1]
        # if record_id <= 0:
        pull = commit_url.split('pull/')[1].split('/')[0]

        review_url = record.get('review_url', None)
        if review_url: comment = get_comment(review_url)
        else:comment, review_url = get_comment_info(repo, pull, review)
        if comment:
            comment_info = {
                "original_position": comment["original_position"],
                "original_start_line": comment["original_start_line"],
                "original_line": comment["original_line"],
                "diff_hunk": comment["diff_hunk"],
            }
        else:
            comment_info = None
        
        #获取commit_hash的parents_commit_hash，将项目回溯到parents_commit_hash的状态
        parents_commit_hash = get_commit_info(repo, commit_hash).get('parents', [])[0]['sha']
        successful_checkout, applied_commits = restore_to_commit(repo, repo_path, parents_commit_hash)
        # successful_checkout = True
        if successful_checkout:
            for commit_info in reversed(applied_commits):
                files = commit_info.get('files', [])
                for file_info in files:
                    try:
                        apply_patch(repo_path, file_info)
                        print(f"Applied patch for {file_info['filename']} commit_info:{commit_info['sha']}")
                    except PermissionError:
                        #有可能是windows将子模块目录当文件处理
                        print(f"Error,failed to apply patch for {file_info['filename']} commit_info:{commit_info['sha']}")
            paths_str, code_diff_str = get_commit_details(repo, commit_url)
            with open(file_path, 'r', encoding='utf-8') as file:
                records = json.load(file)
                for record in records:
                    if record['_id'] == id:
                        record['review_url'] = review_url
                        record['path'] = paths_str
                        record['code_diff'] = code_diff_str
                        record['comment'] = comment_info
                        with open(file_path, 'w', encoding='utf-8') as file:
                            json.dump(records, file, indent=4)
                        print(f"Updated record {record_id} in {file_path}")
                        break
            success_count += 1
        else:
            print(f"Failed to restore commit {commit_hash} for ID {record_id}")
            failure_count += 1
            raise Exception("Failed to restore commit")
        
        processed_count += 1
    return successful_checkout

def CLBPP(record):
    if not record: return None
    record_id, repo, commit_url, review = record["_id"], record["repo"], record["commit_url"], record["review"]
    repo_path = f"/mnt/ssd2/wangke/CR_data/repo/{repo.split('/')[1]}"
    commit_hash = commit_url.split('/')[-1]
    pull = commit_url.split('pull/')[1].split('/')[0]
    review_url = record.get('review_url', None)
    if review_url: comment = get_comment(review_url)
    else:comment, review_url = get_comment_info(repo, pull, review)
    if comment:
        comment_info = {
            "original_position": comment["original_position"],
            "original_start_line": comment["original_start_line"],
            "original_line": comment["original_line"],
            "diff_hunk": comment["diff_hunk"],
        }
    else:
        comment_info = None
    
    #获取commit_hash的parents_commit_hash，将项目回溯到parents_commit_hash的状态
    parents_commit_hash = get_commit_info(repo, commit_hash).get('parents', [])[0]['sha']
    successful_checkout, applied_commits = restore_to_commit(repo, repo_path, parents_commit_hash)
    # successful_checkout = True
    if successful_checkout:
        for commit_info in reversed(applied_commits):
            files = commit_info.get('files', [])
            for file_info in files:
                try:
                    apply_patch(repo_path, file_info)
                    print(f"Applied patch for {file_info['filename']} commit_info:{commit_info['sha']}")
                except PermissionError:
                    #有可能是windows将子模块目录当文件处理
                    print(f"Error,failed to apply patch for {file_info['filename']} commit_info:{commit_info['sha']}")
        paths_str, code_diff_str = get_commit_details(repo, commit_url)
        record['review_url'] = review_url
        record['path'] = paths_str
        record['code_diff'] = code_diff_str
        record['comment'] = comment_info
        print(f"Successfully processed record {record_id}")
        return record
    else:
        print(f"Failed to restore commit {commit_hash} for ID {record_id}")
        raise Exception("Failed to restore commit")

# 主函数
def main(id):
    # file_path = '/mnt/ssd2/wangke/CR_data/dataset/cacr_python_all.json'
    
    # with open(file_path, 'r', encoding='utf-8') as file:
    #     records = json.load(file)
    #     ids = [record['_id'] for record in records]
    # for id in ids:
    #     try:
    #         generate_path_code_diff_to_jsonfile(id, file_path)
    #     except Exception as e:
    #         print(f"Error processing ID {id}: {e}")
    #         continue
    # return generate_path_code_diff_to_jsonfile(id, '/mnt/ssd2/wangke/CR_data/dataset/cacr_python_all.json')
    return generate_path_code_diff_to_jsonfile(id, '/mnt/ssd2/wangke/dataset/sample.json')
    
if __name__ == "__main__":
    main(1)
