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

# 获取数据库中的信息
def get_db_info():
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT _id, repo, context, old, new, review FROM cacr_py WHERE context is not null;")
    while True:
        record = cursor.fetchone()
        if record is None:
            break
        yield record

# 主函数
def main():
    for record in get_db_info():
        record_id, repo, context, old, new, review = record
        print(f"{record_id}:{repo}")
        print(review)
        print(old)
        print("new:")
        print(new)
        

if __name__ == "__main__":
    main()