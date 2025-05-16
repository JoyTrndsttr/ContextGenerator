from getProjectCommitState import get_comment_info
from getProjectCommitState import check_CR_CRN_data
import json
import traceback
config = {
    "dataset_path": "/mnt/ssd2/wangke/CR_data/dataset/cacr_python_all.json",
    "log_path" : "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/log_for_debug.json"
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

with open(config['log_path'], 'r') as f00, open(config["dataset_path"], "r") as f:
    count = json.load(f00)
    # if not count:
    if True:
        count = {
            "Total": 0,
            "Successful_processed": 0,
            "Failed_processed": 0
        }
    
    # records = [json.loads(line) for line in f]
    records = json.load(f)
    records = records[count["Total"]:]
    records = [record for record in records if record["_id"] == -644]
    for record in records:
        count["Total"] += 1
        try:
            if check_CR_CRN_data(record):
                count["Successful_processed"] += 1
            else:
                count["Failed_processed"] += 1
            print(f"Successful: {record['_id']} ; {count['Successful_processed']}/{count['Total']}")
        except Exception as e:
            print(f"Failed: {record['_id']}, {e}")
            traceback.print_exc()
            try:
                key = e.args[0]
            except:
                key = "Others"
            count[key] = count.get(key, 0) + 1
        # with open(config['log_path'], 'w') as f0:
        #     count_str_keys = {str(k): v for k, v in count.items()}
        #     json.dump(count_str_keys, f0, indent=4)