import json
from RequestLLMByApi import RequestLLMByApi
import time
import traceback

request_llm_by_api = RequestLLMByApi()
data_file = "/mnt/ssd2/wangke/dataset/AgentRefiner/final_datasets/cleaned_datasets.json"
output_file = "/mnt/ssd2/wangke/dataset/AgentRefiner/final_datasets/cleaned_datasets_with_analysis.json"
java_config = {
    "data_file": "/data/DataLACP/wangke/recorebench/java/datasets/cleaned_datasets.json",
    "output_file": "/data/DataLACP/wangke/recorebench/java/datasets/cleaned_datasets_with_analysis.json"
}
js_config = {
    "data_file": "/data/DataLACP/wangke/recorebench/js/datasets/cleaned_datasets.json",
    "output_file": "/data/DataLACP/wangke/recorebench/js/datasets/cleaned_datasets_with_analysis.json"
}
config = js_config
data_file = config.get("data_file")
output_file = config.get("output_file")

def get_analysis(record):
    try:
        code_diff, review, review_line, NIDS = record["diff_hunk"], record["review"], record["comment"]["review_position_line"], record.get("new_added_identifiers_definition_strict", [])
        code_diff = '\n'.join(code_diff.split("\n")[1:])
        prompt = request_llm_by_api.prompt_for_estimate_dataset(code_diff, review, review_line, NIDS)
        print(prompt)
        record["prompt_for_deepseek_r1"] = prompt
        record["analysis_by_deepseek_r1"] = request_llm_by_api.get_deepseek_response(prompt)
        return record
    except Exception as e:
        print(e)
        traceback.print_exc()
        return record

def store_record(record):
    with open(output_file, "a", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False)
        f.write("\n")
        id = record["_id"]
        print(f"Saved record {id}")

print("正在等待")
time.sleep(4800)
print("开始处理")

with open(data_file, "r", encoding="utf-8") as f:
    records = [json.loads(line) for line in f]
    last_saved_id = 0
    for i, record in enumerate(records):
        if record["_id"] == 61968:
            last_saved_id = i
            break
    records = records[last_saved_id+1:]

for record in records:
    if not record.get("analysis_by_deepseek_r1", None):
        store_record(get_analysis(record))