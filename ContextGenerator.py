import psycopg2
from psycopg2 import sql
import getContext
import getProjectCommitState
import logging

# Setting up logging
logging.basicConfig(filename='log.txt', level=logging.ERROR, format='%(asctime)s:%(levelname)s:%(message)s')

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
    cursor.execute("SELECT _id from cacr_py")
    while True:
        record = cursor.fetchone()
        if record is None:
            break
        yield record

# 主函数
def main():
    for record in get_db_info():
        id = record[0]
        if id > 9408 : continue
        print(f'processing: {id}')
        try:
            successful_checkout = getProjectCommitState.main(id)
            if successful_checkout:
                getContext.main(id)
        except Exception as e:
            print(f'Error processing ID {id}: {e}')
            logging.error(f'Error processing ID {id}: {e}', exc_info=True)  # Log error with stack trace
    

    # id = 408
    # print(f'processing: {id}')
    # successful_checkout = getProjectCommitState.main(id)
    # if successful_checkout:
    #     getContext.main(id)

if __name__ == "__main__":
    main()