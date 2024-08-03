import psycopg2
from psycopg2 import sql
import subprocess
import requests
import os
import json
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# 数据库连接配置
db_config = {
    'dbname': 'HCGGraph',
    'user': 'user',
    'password': '123456',
    'host': 'localhost',
    'port': '5432'
}

# GitHub 个人访问令牌
GITHUB_TOKEN = ''

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

# 获取数据库中的信息
def get_db_info(id):
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    # cursor.execute("SELECT id, repo, commit_hash, pr_id FROM cacr WHERE repo = 'spotify/luigi';")
    cursor.execute("SELECT id, repo, commit_hash, pr_id FROM cacr WHERE id = %s;", [id])
    record = cursor.fetchone()
    conn.close()
    return record
    # while True:
    #     record = cursor.fetchone()
    #     if record is None:
    #         break
    #     yield record
    # conn.close()

# 使用 GitHub API 获取 commit 信息
def get_commit_info(repo, commit_sha):
    url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests_retry_session().get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()

# 应用文件的补丁
def apply_patch(patch, file_path):
    # 检查文件是否存在，不存在则创建
    dir_name = os.path.dirname(file_path)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write('')

    with open(file_path, 'r', encoding='utf-8') as file:
        file_content = file.readlines()
    
    start_line = None
    line_change = 0 #补丁所在行修正
    # 解析补丁并应用到文件
    for line in patch.split('\n'):
        if line.startswith('@@'):
            start_line = int(line.split()[1].split(',')[0][1:]) - 2 + line_change
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

# 存储commit信息
def store_commit_details(repo, commit_sha):
    commit_info = get_commit_info(repo, commit_sha)
    files = commit_info.get('files', [])

    paths = []
    code_diff = {}
    
    for file_info in files:
        paths.append(file_info['filename'])
        code_diff[file_info['filename']] =  file_info['patch']

    paths_str = '\n'.join(paths)
    code_diff_str = json.dumps(code_diff)

    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE cacr
        SET path = %s, code_diff = %s
        WHERE commit_hash = %s;
    """, (paths_str, code_diff_str, commit_sha))
    conn.commit()
    cursor.close()
    conn.close()

# 还原到特定 commit
def restore_to_commit(repo, repo_path, target_commit):
    current_commit = target_commit
    search_count = 0
    successful_checkout = False
    applied_commits = []

    while search_count < MAX_PARENT_SEARCH:
        try:
            subprocess.run(["git", "checkout", current_commit, "-f"], cwd=repo_path, check=True)
            print(f"Successfully checked out to commit {current_commit}")
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

# 主函数
def main(id):

    processed_count = 0
    success_count = 0
    failure_count = 0
    
    record = get_db_info(id)
    if record:
        record_id, repo, commit_hash, pr_id = record
        repo_path = os.path.join('repo', repo.split('/')[1])
        
        #获取commit_hash的parents_commit_hash，将项目回溯到parents_commit_hash的状态
        parents_commit_hash = get_commit_info(repo, commit_hash).get('parents', [])[0]['sha']
        successful_checkout, applied_commits = restore_to_commit(repo, repo_path, parents_commit_hash)

        if successful_checkout:
            for commit_info in reversed(applied_commits):
                files = commit_info.get('files', [])
                for file_info in files:
                    if 'patch' in file_info:
                        patch = file_info['patch']
                        file_path = os.path.join(repo_path, file_info['filename'])
                        apply_patch(patch, file_path)
                        print(f"Applied patch for {file_info['filename']}")
            store_commit_details(repo, commit_hash)
            success_count += 1
        else:
            print(f"Failed to restore commit {commit_hash} for ID {record_id}")
            failure_count += 1
        
        processed_count += 1

if __name__ == "__main__":
    main()
