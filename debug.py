from getProjectCommitState import get_comment_info
import json
import traceback
config = {
    "dataset_path": "/mnt/ssd2/wangke/CR_data/dataset/cacr_python_all.json",
}

with open(config["dataset_path"], "r") as f:
    # records = [json.loads(line) for line in f]
    records = json.load(f)
    # records = [record for record in records if record["repo"] == "spotify/luigi"]
    print(len(records))
    count = [0,0]
    for record in records:
        id = record["_id"]
        try:
            comment_info = get_comment_info(record)
            count[0] += 1
            print(f"Successful: {id}")
        except Exception as e:
            print(f"Failed: {id}, {e}")
            traceback.print_exc()
            count[1] += 1
    print(f"Successful: {count[0]}, Failed: {count[1]}")
