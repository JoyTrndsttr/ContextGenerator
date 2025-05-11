from getProjectCommitState import get_comment_info
import json
import traceback
config = {
    # "dataset_path": "/mnt/ssd2/wangke/CR_data/dataset/cacr_python_all.json",
    "dataset_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_datasets_all_filtered_5.json",
    "output_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_repo_datasets_filtered_restrict_2.json"
}

# with open(config["dataset_path"], "r") as f:
#     # records = [json.loads(line) for line in f]
#     records = json.load(f)
#     records = [record for record in records if record["_id"] > 0]
#     print(len(records))
#     count = [0,0]
#     for record in records:
#         id = record["_id"]
#         try:
#             comment_info = get_comment_info(record)
#             count[0] += 1
#             print(f"Successful: {id}")
#         except Exception as e:
#             print(f"Failed: {id}, {e}")
#             traceback.print_exc()
#             count[1] += 1
#     print(f"Successful: {count[0]}, Failed: {count[1]}")

with open(config["output_path"], "a") as f0:
    with open(config["dataset_path"], "r") as f:
        records = [json.loads(line) for line in f]
        count = 0 
        successful_count = 0
        for record in records:
            count += 1
            try:
                comment_info, review_url = get_comment_info(record)
                record["review_url"] = review_url
                successful_count += 1
                print(f"Successful: {record['_id']} ; {successful_count}/{count}")
                f0.write(json.dumps(record, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"Failed: {record['_id']}, {e}")
                traceback.print_exc()