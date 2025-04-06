import json
import model
from AgentRefiner import AgentRefiner
import re
# config = {
#     "dataset_path": "/mnt/ssd2/wangke/dataset/datasets.json",
#     "output_path": '/mnt/ssd2/wangke/dataset/map_result/',
#     "record_path": '/mnt/ssd2/wangke/dataset/map_result/llama_map.json',
#     "result_path": '/mnt/ssd2/wangke/dataset/map_result/llama_result.json'
# }
config = {
    "dataset_path": "/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_llama.json",
    "output_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/CR_and_CRN.json"
}

def get_json_value_number(str, key):
    try:
        return re.search(r'(\d+)', str.split(key)[1]).group(0)
    except:
        return "0"

def get_json_value_string(str, key):
    try:
        return re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', str).group(1)
    except:
        return ""
    
with open(config['output_path'], 'a') as f0:
    with open(config['dataset_path'], 'r') as f:
        # records = [json.loads(line) for line in f]
        records = json.load(f)
        # records = [records[0]]
        for record in records:
            print(f"Processing {record['_id']}")
            prompt_for_repo_context_dependency_estimation = model.prompt_for_repo_context_dependency_estimation(record["old"], record["review"], record["new"])
            _, think_for_repo_context_dependency_estimation, repo_context_dependency_estimation_result_json = model.get_full_deepseek_response(prompt_for_repo_context_dependency_estimation)
            record["repo_context_dependency_estimation"] = {
                "Additional_context_required":get_json_value_number(repo_context_dependency_estimation_result_json, "Additional_context_required"),"
                "Reason_for_require_additional_context": get_json_value_string(repo_context_dependency_estimation_result_json, "Reason_for_require_additional_context"),
                "Think_for_repo_context_dependency_estimation": think_for_repo_context_dependency_estimation.split('\n')
            }
            f0.write(json.dumps(record, ensure_ascii=False) + '\n')