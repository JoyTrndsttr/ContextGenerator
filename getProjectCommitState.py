import subprocess
import os
import shutil
import json
from utils.RequestGitHub import RequestGitHub
import re
import traceback

# 用来控制获取的GitHub token
requestGitHub = RequestGitHub()

# 最大查找 parent commit 的次数
MAX_PARENT_SEARCH = 100

config = {
    "base_repo_dir" : f"/data/DataLACP/wangke/recorebench/repo/repo/"
}

# 清空特定路径下所有文件
# def clear(path):
#     for filename in os.listdir(path):
#         try:
#             full_path = os.path.join(path, filename)
#             if os.path.isfile(full_path) or os.path.islink(full_path):
#                 os.remove(full_path)
#             elif os.path.isdir(full_path):
#                 shutil.rmtree(full_path)
#         except Exception as e:
#             print(f"Failed to delete {full_path}: {e}")
def clear(path):
    try:
        # 获取所有子文件夹，并附上创建时间
        folders = [
            (os.path.join(path, d), os.path.getctime(os.path.join(path, d)))
            for d in os.listdir(path)
            if os.path.isdir(os.path.join(path, d))
        ]

        # 按创建时间降序排列（新 -> 旧）
        folders.sort(key=lambda x: x[1], reverse=True)

        # 多余的（第21个及之后的）删除
        for folder_path, _ in folders[20:]:
            try:
                shutil.rmtree(folder_path)
                print(f"Deleted old folder: {folder_path}")
            except Exception as e:
                print(f"Failed to delete {folder_path}: {e}")

    except Exception as e:
        print(f"Failed to clear path {path}: {e}")

# 重置repo状态
def reset_repo(repo):
    repo_path = config["base_repo_dir"] + repo.split('/')[1]
    try:
        if os.path.exists(repo_path):
            subprocess.run(["rm", "-f", ".git/index.lock"], cwd=repo_path, check=True)
            subprocess.run(["git", "reset", "--hard"], cwd=repo_path, check=True)
    except Exception as e:
        print(f"Failed to reset repo {repo}: {e}")


#获取Json文件中的信息
def get_info_from_jsonfile(file_path, id):
    with open(file_path, 'r', encoding='utf-8') as file:
        records = json.load(file)
        for record in records:
            if record['_id'] == id:
                return record

# 使用 GitHub API 获取 commit 信息
def get_commit_info(repo, commit_sha):
    url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
    full_content = requestGitHub.get_full_content(url)
    if not full_content: raise Exception(f"Failed to get commit info for {commit_sha}")
    if len(full_content) == 1: return full_content[0]
    else:
        commit_infos = full_content[0]
        for i in range(1, len(full_content)):
            commit_infos['files'].extend(full_content[i]['files'])
        return commit_infos

# 使用 GitHub API 获取评论信息
def get_comment_info(record):
    def normalize_text(text):
        text = re.sub(r'\W+','', text)
        return text

    # if not record.get("original_review", None): record["original_review"] = record["review"]
    repo, review, commit_url = record["repo"],record["review"],record["commit_url"]
    old_lines = [line[1:] for line in record["old"].split('\n')]
    pull = commit_url.split('pull/')[1].split('/')[0]
    review_url = f"https://api.github.com/repos/{repo}/pulls/{pull}/comments"
    comments = requestGitHub.get_response(review_url).json()
    _comment = None
    for comment in comments:
        if normalize_text(comment['body']) == normalize_text(review):
            _comment = comment
            break
    if _comment:
        comment_info = {
            "original_position": _comment["original_position"],
            "original_start_line": _comment["original_start_line"],
            "original_line": _comment["original_line"],
            "diff_hunk": _comment["diff_hunk"],
            "review_position_line": _comment["diff_hunk"].split('\n')[-1][1:], #一般来说最后一行是review指向的行
        }
        diff_hunk_lines = _comment["diff_hunk"].split('\n')
        start = int(re.search(r'(\d+)', diff_hunk_lines[0]).group(1))
        if _comment["original_start_line"]:
            try:
                comment_info["review_hunk_start_line"] = diff_hunk_lines[_comment["original_start_line"]-start+1][1:] #加1是因为第一行是code_diff_hunk的prefix
                if comment_info["review_hunk_start_line"] not in old_lines:
                    print(f"Error finding start position of comment in old code: id:{record['_id']}")
                    raise Exception(f"Error finding start position of comment in old code")
            except Exception as e:
                print(f"{e}, id:{record['_id']}")
                comment_info["original_start_line"] = None
                comment_info["review_hunk_start_line"] = None
        comment_info['review_position_line'] = diff_hunk_lines[-1][1:]
        if comment_info['review_position_line'] not in old_lines:
            print(f"Error finding position of comment in old code: id:{record['_id']}")
            raise Exception(f"Error finding position of comment in old code")
        return comment_info, _comment['url']
    else:
        return None, review_url

# 检查CR/CRN数据
def check_CR_CRN_data(record):
    def normalize_text(text):
        text = re.sub(r'\W+','', text)
        return text
    def check_parents_commit(repo, commit_sha, original_commit_sha, original_commit_time):
        url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
        commit = requestGitHub.get_response(url).json()
        if commit_sha == original_commit_sha: return True
        elif commit['commit']['committer']['date'] < original_commit_time:
            return False
        else:
            parents = commit["parents"]
            for parent in parents: return check_parents_commit(repo, parent["sha"], original_commit_sha, original_commit_time)
            return False
    
    repo, review, commit_url = record["repo"],record["review"],record["commit_url"]
    commit_hash = commit_url.split('/')[-1]
    if record.get("review_url", None): review_url = record["review_url"]
    else:
        pull = commit_url.split('pull/')[1].split('/')[0]
        full_review_url = f"https://api.github.com/repos/{repo}/pulls/{pull}/comments"
        _comment = None
        for page in range(1, 100):
            flag = False
            comments = requestGitHub.get_response_by_page(full_review_url, page).json()
            if not comments: break
            for comment in comments:
                if normalize_text(comment['body']) == normalize_text(review):
                    _comment = comment
                    flag = True
                    break
            if flag: break
        if not _comment:
            print(f"Failed to find review, id:{record['_id']}")
            raise Exception(f"Wrong linking")
        review_url = _comment['url']
        diff_hunk_lines = _comment["diff_hunk"].split('\n')
        review_position_line = diff_hunk_lines[-1][1:]
        old_lines = [line[1:] for line in record["old"].split('\n')]
        if review_position_line not in old_lines:
            print(f"Error finding position of comment in old code: id:{record['_id']}")
            raise Exception(f"Error finding position of comment in old code")

    comment_info = get_comment(review_url)
    original_commit_hash = comment_info["original_commit_id"]
    commit_info = get_commit_info(repo, commit_hash)
    original_commit = f"https://api.github.com/repos/{repo}/commits/{original_commit_hash}"
    original_commit_info = requestGitHub.get_response(original_commit).json()
    if not check_parents_commit(repo, commit_info['sha'], original_commit_info["sha"], original_commit_info['commit']['committer']['date']):
        raise Exception(f"Failed_processed")
    old_lines = [line[1:].strip() for line in record["old"].split('\n')]
    new_lines = [line[1:].strip() for line in record["new"].split('\n')]
    lines = old_lines + new_lines
    path = comment_info['path']
    files = commit_info.get('files', [])
    match_flag = False
    for file in files:
        hunks = []
        if file['filename'] == path:
            patch = file.get('patch', '')
            if not patch:
                print(f"Can not find file path in CRA, id:{record['_id']}")
                raise Exception(f"Diff hunk not found")
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
                hunk_lines = [line[1:].strip() for line in hunk_lines]   
                #如果lines的每一行都在hunk中，则匹配成功
                if all(line in hunk_lines for line in lines):
                    match_flag = True
            if match_flag: break
            else: 
                print(f"Diff hunk not found, id:{record['_id']}")
                raise Exception(f"Diff hunk not found")
    if not match_flag: 
        print(f"Can not find file path in CRA, id:{record['_id']}")
        raise Exception(f"Can not find file path in CRA")
    return True

def get_comment(review_url):
    return requestGitHub.get_response(review_url).json()

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

def CLBPP(record):
    if not record: return None
    record_id, repo, commit_url, review_url = record["_id"], record["repo"], record["commit_url"], record["review_url"]
    # repo_path = f"/mnt/ssd2/wangke/CR_data/repo/{repo.split('/')[1]}"
    repo_path = f"/data/DataLACP/wangke/recorebench/repo/repo/{repo.split('/')[1]}"
    commit_hash = commit_url.split('/')[-1]
    
    #获取commit_hash的parents_commit_hash，将项目回溯到parents_commit_hash的状态
    parents_commit_hash = get_commit_info(repo, commit_hash).get('parents', [])[0]['sha']
    successful_checkout, applied_commits = restore_to_commit(repo, repo_path, parents_commit_hash)
    if successful_checkout:
        for commit_info in reversed(applied_commits):
            files = commit_info.get('files', [])
            for file_info in files:
                try:
                    apply_patch(repo_path, file_info)
                    print(f"Applied patch for {file_info['filename']} commit_info:{commit_info['sha']}")
                except PermissionError:
                    print(f"Error,failed to apply patch for {file_info['filename']} commit_info:{commit_info['sha']}")
        review_info = requestGitHub.get_response(review_url).json()
        record['path'] = review_info['path']
        print(f"Successfully processed record {record_id}")
        return record
    else:
        print(f"Failed to restore commit {commit_hash} for ID {record_id}")
        raise Exception("Failed to restore commit")

#
def fill_record(record):
    record_id, repo, path, commit_url, review_url = record["_id"], record["repo"], record["path"], record["commit_url"], record["review_url"]
    repo_path = f"/data/DataLACP/wangke/recorebench/repo/repo/{repo.split('/')[1]}"
    file_path = os.path.join(repo_path, path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_file = f.readlines()
    except FileNotFoundError:
        print(f"Error, file {file_path} not found")
    

# 主函数
def main(id):
    pass
    
if __name__ == "__main__":
    main(1)
