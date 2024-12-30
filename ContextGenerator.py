import psycopg2
from psycopg2 import sql
from ContextGenerators.getContextGenerators import LanguageContextGenerator
import getProjectCommitState
import logging
import ErrorProcess
import json
import model
import re
import traceback

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
    # with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_test_with_llama_all.json', 'w') as f0:
    with open('/mnt/ssd2/wangke/CR_data/dataset/dataset_all.json', 'w') as f0:
        f0.write('[\n')
        first_record = True
        with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_all.json', 'r') as f:
            records = json.load(f)
            new_records = []
            for record in records:
                try:
                    # if not record['_id'] > 0 : continue
                    # if not record['_id'] == _id: continue
                    id = record['_id']
                    print(f'processing: {id}')
                    old_without_minus = model.remove_prefix(record['old'])
                    new_without_plus = model.remove_prefix(record['new'])
                    new = record['new']

                    # 获取仓库在commit提交前的状态
                    attempt = 0
                    while attempt < 1:
                        try:
                            successful_checkout = getProjectCommitState.main(id)
                            if successful_checkout:
                                break
                        except Exception as e:
                            attempt += 1
                            print(f'Error processing ID {id}: {e}')
                            if attempt == 1 :
                                logging.error(f'Error processing ID {id}: {e}', exc_info=True)  # Log error with stack trace
                                raise Exception(f'获取仓库在commit提交前的状态失败')
                    
                    #ReAct框架 
                    turn, flag_for_more_info, flag_for_context_change = 0, True, True
                    
                    languageContextGenerator = LanguageContextGenerator(id)
                    if not languageContextGenerator: return None
                    contextGenerator = languageContextGenerator.context_generator
                    calls = [] #元组格式，（调用的函数，被调用的函数，被调用函数的实现）
                    results = [] #存储每一个turn的结果
                    name = "" #存储要检索的函数名

                    while turn < 6 and flag_for_more_info and flag_for_context_change:
                        turn += 1
                        print(f"turn {turn}")
                        if name: contextGenerator.updateSource(name)
                        definitions = contextGenerator.getContext()
                        result = {"turn": turn, "prompt_for_refinement": "", "result_json": "", "prompt_for_instruction": "", "em": 0, "em_trim": 0, "bleu": 0, "bleu_trim": 0}
                        
                        max_attempts = 3
                        # 第二步：根据context、old_code和review生成new_code，并评估结果（这里放前面是要不加context先评估一次）
                        for i in range(max_attempts):
                            #TODO:需要更改prompt的长度，设置限制
                            result["prompt_for_refinement"] = model.prompt_for_refinement(old_without_minus, record["review"], calls)
                            new_code, answer = model.get_model_response(result["prompt_for_refinement"])
                            if not new_code: continue
                            new_code_lines = new_code.split('\n')
                            #用于去除new_code多生成的代码补全
                            if not result["turn"] == 1: 
                                end_line = record["old"].split('\n')[-1][1:]
                                index = -1
                                for i, line in enumerate(new_code_lines):
                                    if line.strip() == end_line.strip():
                                        index = i
                                if index != -1:
                                    new_code_lines = new_code_lines[:index+1]
                                    print(f"已在new_code中截取到{end_line}")
                                else: 
                                    print(f"没有在new_code中找到{end_line}")
                            em, em_trim, bleu, bleu_trim = model.calc_em_and_bleu(new, new_code)
                            if bleu + bleu_trim > result["bleu"] + result["bleu_trim"]: #取最好值
                                result["em"], result["em_trim"], result["bleu"], result["bleu_trim"] = em, em_trim, bleu, bleu_trim
                                result["new_code"] = new_code_lines
                                result["new_code_groud_truth"] = new.split('\n')

                        # 第一步：判断是否要继续寻找information，给出要查找的函数名
                        flag_for_context_change = False    #用于判断模型有没有给出有效的函数名以继续查找context
                        for i in range(max_attempts):
                            result["prompt_for_instruction"] = model.prompt_for_instruction(old_without_minus, record["review"], calls)
                            answer_code, result["result_json"] = model.get_model_response(result["prompt_for_instruction"])
                            if not result["result_json"]: continue
                            # flag = re.findall(r'"need more information\?": "(.*?)",', result_json)[0]
                            # if not flag: continue
                            # flag = False if flag == "False" else True
                            name = re.findall(r'"function_name": "(.*?)",', result["result_json"])
                            if len(name) == 0: continue
                            name = name[0]
                            #在definitions中查找name，并存入函数调用关系以及被调用函数的实现
                            
                            definition_name = next((definition for definition in definitions if definition['name'] == name), None)
                            if definition_name:
                                exist_name = next((call[1] for call in calls if call[1] == name), None)
                                if exist_name: continue #如果已经存在该函数的调用关系，则跳过
                                calls.append((definition_name['caller'], name, definition_name['text']))
                                flag_for_context_change = True
                                break
                        #调整result的格式以方便阅读
                        result["prompt_for_instruction"] = result["prompt_for_instruction"].split('\n')
                        result["prompt_for_refinement"] = result["prompt_for_refinement"].split('\n')
                        result["result_json"] = result["result_json"].split('\n')
                        result["new_code_groud_truth"] = record["new"].split('\n')
                        results.append(result)
                    
                    record["results"] = results
                    record["context"] = json.dumps(definitions)
                    record["llama_em"] = sum(result["em"] for result in results)/len(results)
                    record["llama_em_trim"] = sum(result["em_trim"] for result in results)/len(results)
                    record["llama_bleu"] = sum(result["bleu"] for result in results)/len(results)
                    record["llama_bleu_trim"] = sum(result["bleu_trim"] for result in results)/len(results)

                    #写入文件
                    if not first_record:
                        f0.write(',\n')  # 写入逗号和换行
                    first_record = False
                    json.dump(record, f0, indent=4)
                    new_records.append(record)

                except Exception as e:
                    print(f'Error processing ID {id}: {e}')
                    traceback.print_exc()
            print(f"All {len(new_records)} records processed")
        f0.write('\n]')
if __name__ == "__main__":
    main(0)