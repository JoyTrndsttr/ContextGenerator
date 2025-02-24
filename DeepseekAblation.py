# import requests
# from utils.RequestLLM import RequestLLM
# import json
# import model

# requestLLM = RequestLLM()
# file_path = "/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted.json"
# output_path = "/mnt/ssd2/wangke/CR_data/dataset/map_result/tmp.json"
# # output_path = "/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_deepseek.json"
# with open(file_path, "r") as f:
#     records = json.load(f)
#     for record in records:
#         _record = {}
#         _record["id"] = record["_id"]
#         if record["_id"] != -115:continue
#         print(f"processing: {_record['id']}")
#         _record["results"] = []
#         for turn_result in record["results"]:
#             _record["results"].append(turn_result["ablation_results"][1])
#         for result in _record["results"]:
#             prompt = '\n'.join(result["prompt_for_refinement"])
#             result["new_code"] = requestLLM.request_deepseek(prompt, record["old"])
#             if result["new_code"]:
#                 result["em"], result["em_trim"], result["bleu"], result["bleu_trim"] = model.calc_em_and_bleu(record["new"], result["new_code"])
#                 result["new_code"] = result["new_code"].split("\n")
#             else:
#                 result["em"], result["em_trim"], result["bleu"], result["bleu_trim"] = 0, 0, 0, 0
#         with open(output_path, "a", encoding="utf-8") as f1:
#             f1.write(json.dumps(_record) + "\n")

import requests
from utils.RequestLLM import RequestLLM
import json
import model
import threading
from concurrent.futures import ThreadPoolExecutor

# 创建线程安全的文件写入锁
file_lock = threading.Lock()
# 访问deepseek的设置
config={
    "max_tokens": 3000,
    "do_sample": True,
    "repetition_penalty": 1.02,
    "temperature": 0,
    "port" : 8000
}

def process_record(record, output_path):
    _record = {
        "id": record["_id"],
        "results": []
    }
    print(f"processing: {_record['id']}")
    
    try:
        # 处理每个turn的结果
        for turn, turn_result in enumerate(record.get("results", [])):
            _result = {
                "turn" : turn + 1,
                "ablation_results": []
            }
            # 仅保留第二个ablation_result（索引1）
            if len(turn_result["ablation_results"]) > 1:
                for index, ablation_result in enumerate(turn_result["ablation_results"]):
                    if index < 4: continue # 只保留前4个ablation_result
                    selected_result = ablation_result
                    # 生成prompt并请求模型
                    prompt = '\n'.join(selected_result["prompt_for_refinement"])
                    if turn > 0:
                        prev_codes = []
                        for prev_code_index in range(turn):
                            prev_code = record["results"][prev_code_index]["ablation_results"][index]["new_code"]
                            if prev_code: prev_codes.append('\n'.join(prev_code))
                        if len(prev_codes) > 0:
                            prompt += "\nHere is the previously generated code. You can select the version that" \
                                      " a human reviewer is most likely to choose or modify it as needed:" \
                                      " Your sole purpose is to modify the code based on the reviewer's comments."\
                                      " The provided functions are only meant to assist you in this task."
                            for prev_code in prev_codes:
                                prompt += f'\n```\n{prev_code}\n```'
                        
                    selected_result["new_code"], think, output = RequestLLM().request_deepseek(prompt, config)
                    if prompt:
                        selected_result["prompt_for_refinement"] = prompt.split("\n")
                    if think:
                        selected_result["think"] = think.split("\n")
                    else:
                        selected_result["think"] = []
                    
                    # 计算结果指标
                    if selected_result["new_code"]:
                        em, em_trim, bleu, bleu_trim = model.calc_em_and_bleu(
                            record["new"], 
                            selected_result["new_code"]
                        )
                        selected_result.update({
                            "em": em,
                            "em_trim": em_trim,
                            "bleu": bleu,
                            "bleu_trim": bleu_trim,
                            "new_code": selected_result["new_code"].split("\n")
                        })
                    else:
                        selected_result.update({
                            "em": 0,
                            "em_trim": 0,
                            "bleu": 0, 
                            "bleu_trim": 0
                        })
                    _result["ablation_results"].append(selected_result)
            _record["results"].append(_result)
        # 线程安全的文件写入
        with file_lock:
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(_record) + "\n")
                
    except Exception as e:
        print(f"Error processing record {_record['id']}: {str(e)}")
        # 可以选择记录错误日志

if __name__ == "__main__":
    # 初始化配置
    input_file = "/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_llama.json"
    # output_file = "/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_ablation_deepseek2.json"
    output_file = "/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_ablation_deepseek_default.json"
    
    # 加载已处理的数据
    processed_ids = []
    with open(output_file, 'r') as f:
        processed_records = []
        for line in f:
            processed_record = json.loads(line.strip())
            processed_ids.append(processed_record["id"])
    print(f"Processed {len(processed_ids)} records")
    
    # 加载数据
    with open(input_file, "r") as f:
        records = json.load(f)
        # process_record(records[1], output_file)
        records = [record for record in records if record["_id"] not in processed_ids]
    
    # 创建线程池（10个worker）
    with ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有任务
        futures = [
            executor.submit(process_record, record, output_file)
            for record in records
        ]
        
        # 等待所有任务完成（可选）
        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(f"Task failed: {str(e)}")