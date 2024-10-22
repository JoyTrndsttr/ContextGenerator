import psycopg2
from psycopg2 import sql
import getContext
import getProjectCommitState
import logging
import ErrorProcess

# Setting up logging
# logging.basicConfig(filename='log.txt', level=logging.ERROR, format='%(asctime)s:%(levelname)s:%(message)s')

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
    ids = ErrorProcess.error_ids2
    for id in ids:
    # for record in get_db_info():
    #     id = record[0]
        # if id < 2540 : continue
        print(f'processing: {id}')
        attempt = 0
        while attempt < 3:
            try:
                successful_checkout = getProjectCommitState.main(id)
                if successful_checkout:
                    getContext.main(id)
                break
            except Exception as e:
                attempt += 1
                print(f'Error processing ID {id}: {e}')
                if attempt ==3:
                    logging.error(f'Error processing ID {id}: {e}', exc_info=True)  # Log error with stack trace
    

    
    # id = 1408
    # print(f'processing: {id}')
    # successful_checkout = getProjectCommitState.main(id)
    # if successful_checkout:
    #     getContext.main(id)
    # # try:
    # #     successful_checkout = getProjectCommitState.main(id)
    # #     if successful_checkout:
    # #         getContext.main(id)
    # # except Exception as e:
    # #     print(f'Error processing ID {id}: {e}')
if __name__ == "__main__":
    main()