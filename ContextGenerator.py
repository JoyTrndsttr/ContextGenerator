import psycopg2
from psycopg2 import sql
import getContext
import getProjectCommitState
import logging
import ErrorProcess
import json
import model
import re

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

# 从postgres数据库获取所有id
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
def main(_id):
    # ids = ErrorProcess.error_ids2
    with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_test.json', 'r') as f:
        records = json.load(f)
        ids = [record['_id'] for record in records]
        for id in ids:
            # id = _id
            if id != 1 : continue
            print(f'processing: {id}')

            # 获取仓库在commit提交前的状态
            # attempt = 0
            # while attempt < 1:
            #     try:
            #         successful_checkout = getProjectCommitState.main(id)
            #         if successful_checkout:
            #             break
            #     except Exception as e:
            #         attempt += 1
            #         print(f'Error processing ID {id}: {e}')
            #         if attempt ==3:
            #             logging.error(f'Error processing ID {id}: {e}', exc_info=True)  # Log error with stack trace
            #             return None
            
            #ReAct框架 
            turn = 0
            
            context = json.dumps(getContext.main(id))
            record = records[id]
            old_without_minus = model.remove_minus_or_plus(record['old'], '-')
            prompt = model.generate_context_prompt(old_without_minus, record["review"], None)
            result, answer = model.get_model_response(prompt) #result为空的话需要重复几次
            print(f'ReAct: {result}')
            #待匹配的字符串："function_name": "cross_entropy",
            # name = re.findall(r'"function_name": "(.*?)",', result)[0]
            result_json = json.loads(result)
            function_name = result_json['function_name']
            # for func_name, 

            # while turn < 6:
            #     if result and turn < 5 :#and result['Need more information'] == True:
            #         turn += 1
            #         prompt = model.generate_context_prompt(old_without_minus, record["review"], context)
            #         result, answer = model.get_model_response(prompt)
            #     else:
            #         prompt = model.generate_new_prompt5_CRN(old_without_minus, record["review"], context)
            #         result, answer = model.get_model_response(prompt)
            #         break
    

    
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
    main(1)