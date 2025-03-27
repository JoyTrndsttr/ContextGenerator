import json
import model
# input_file = "/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_llama.json"
# input_file = "/mnt/ssd2/wangke/dataset/cr_data/dataset_sorted_llama_instructed.json"
input_file = "/mnt/ssd2/wangke/dataset/datasets.json"
# output_file = "/mnt/ssd2/wangke/dataset/cr_data/dataset_sorted_llama_instructed_map.json"
# output_file = "/mnt/ssd2/wangke/dataset/cr_data/dataset_sorted_llama_instructed_map_deepseek.json"
output_file = "/mnt/ssd2/wangke/dataset/cr_data/new_datasets_instructed_map_deepseek.json"
with open(input_file, "r") as f:
    # records = json.load(f)
    records = [json.loads(line) for line in f]
    for record in records:
        print(f"processing record {record['_id']}")
        old, review, new = record["old"], record["review"], record["new"]
        prompt_for_repository_context_requirement = model.prompt_for_repository_context_requirement(old, review, new)
        _, repository_context_result_json = model.get_deepseek_response(prompt_for_repository_context_requirement)
        record["prompt_for_repository_context_requirement"] = prompt_for_repository_context_requirement.split('\n')
        record["repository_context_result_json"] = repository_context_result_json.split('\n')
        with open(output_file, "a") as f1:
            f1.write(json.dumps(record) + "\n")
            # json.dump(record, f1, indent=4)