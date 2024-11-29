import json
import subprocess
import os
import shutil
import time

# 设置克隆目录
clone_dir = r'C:\\Users\Administrator\\OneDrive - csu.edu.cn\\work\\开源实验室\\科研相关\\安全代码意见\\ContextGenerator\dataset\\repo'

def get_disk_usage(path):
    """ 获取指定路径的磁盘使用信息 (以MB为单位) """
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total_size += os.path.getsize(fp)
            except OSError:
                print(f"Error accessing file {fp}. File may have been moved or deleted.")
    return total_size / (1024 * 1024)  # Convert bytes to MB

def clone_repository(repo_url, full_clone_path):
    """ Attempt to clone a repository with retries """
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            subprocess.run(['git', 'clone', repo_url, full_clone_path], check=True)
            print(f"Successfully cloned {repo_url} into {full_clone_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Attempt {attempt + 1} failed for {repo_url}: {e}")
            time.sleep(5)  # wait for 5 seconds before retrying
    return False

def clone_repositories():
    with open('repo_py.jsonl', 'r') as file:
        repos = file.readlines()
        total = len(repos)  # 总仓库数量
        for i, line in enumerate(repos):
            repo_info = json.loads(line)
            # repo_url = repo_info['repo_url'].replace('github.com', 'githubfast.com')
            repo_url = repo_info['repo_url']
            repo_name = repo_info['repo'].split('/')[-1]
            full_clone_path = os.path.join(clone_dir, repo_name)

            if not os.path.exists(full_clone_path):  # 检查仓库是否已克隆
                print(f"Cloning {repo_name} ({i+1}/{total})")
                if not clone_repository(repo_url, full_clone_path):
                    print(f"Final attempt failed for {repo_name}. Consider manual intervention.")
                else:
                    disk_usage = get_disk_usage(full_clone_path)
                    print(f"Disk usage after cloning {repo_name}: {disk_usage:.2f} MB")
            else:
                disk_usage = get_disk_usage(full_clone_path)
                print(f"Repository {repo_name} already exists at {full_clone_path}. Disk usage: {disk_usage:.2f} MB - Skipping ({i+1}/{total})")

if __name__ == "__main__":
    clone_repositories()
