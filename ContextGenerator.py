import psycopg2
from psycopg2 import sql
import getContext
import getProjectCommitState

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
    cursor.execute("SELECT id from cacr WHERE repo = 'spotify/luigi'")
    while True:
        record = cursor.fetchone()
        if record is None:
            break
        yield record

# 主函数
def main():
    for record in get_db_info():
        id = record[0]
        print(f'processing: {id}')
        getProjectCommitState.main(id)
        getContext.main(id)
    

    # id = 12323
    # print(f'processing: {id}')
    # getProjectCommitState.main(id)
    # getContext.main(id)

if __name__ == "__main__":
    main()