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
    "output_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/CR_and_CRN_4_6.json"
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

def normalize_text(text):
    text = re.sub(r'\W+','', text)
    return text

with open(config['output_path'], 'a') as f0:
    with open(config['dataset_path'], 'r') as f:
        # records = [json.loads(line) for line in f]
        records = json.load(f)
        # records = [records[0]]
        for record in records:
            print(f"Processing {record['_id']}")

            new_line = record["new"].split("\n")
            new_line_add_flag = False
            for line in new_line:
                if line.startswith('+') : new_line_add_flag = True
            if not new_line_add_flag: continue
            if record["review"].find("```") != -1:continue

            if record["review"].find("suggestion") != -1:#含有suggestion的不太可能需要上下文
                continue

            
            old = record["old"]

            comment = record["comment"]
            diff_hunk_lines = comment["diff_hunk"].split('\n')
            start = int(re.findall(r'(\d+)', diff_hunk_lines[0])[2])
            if comment["original_start_line"] and comment["original_start_line"]-start+1 < len(diff_hunk_lines):
                comment["review_hunk_start_line"] = diff_hunk_lines[comment["original_start_line"]-start+1][1:] #加1是因为第一行是code_diff_hunk的prefix
            index = len(diff_hunk_lines)-1 # 指向review_position_line
            for i in range(index, -1, -1):
                line = diff_hunk_lines[i][1:]
                if line:
                    comment["review_position_line"] = line
                    break

            review_line = record["comment"]["review_position_line"]
            flag = False
            for line in old.split("\n"):
                if normalize_text(line) == normalize_text(review_line):
                    flag = True
                    break
            if not flag: continue

            prompt_for_repo_context_dependency_estimation = model.prompt_for_repo_context_dependency_estimation(record["old"], record["review"], record["new"])
            _, think_for_repo_context_dependency_estimation, repo_context_dependency_estimation_result_json = model.get_full_deepseek_response(prompt_for_repo_context_dependency_estimation)
            record["repo_context_dependency_estimation"] = {
                "Additional_context_required": get_json_value_number(repo_context_dependency_estimation_result_json, "Additional_context_required"),
                "Reason_for_require_additional_context": get_json_value_string(repo_context_dependency_estimation_result_json, "Reason_for_require_additional_context"),
                "Think_for_repo_context_dependency_estimation": think_for_repo_context_dependency_estimation.split('\n')
            }

            if record["repo_context_dependency_estimation"]["Additional_context_required"] == "0":
                continue

            f0.write(json.dumps(record, ensure_ascii=False) + '\n')