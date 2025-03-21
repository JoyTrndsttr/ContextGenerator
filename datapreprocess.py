import json
import model
from AgentRefiner import AgentRefiner
import re
config = {
    "dataset_path": "/mnt/ssd2/wangke/dataset/datasets.json",
    "output_path": '/mnt/ssd2/wangke/dataset/map_result/',
    "record_path": '/mnt/ssd2/wangke/dataset/map_result/llama_map.json',
    "result_path": '/mnt/ssd2/wangke/dataset/map_result/llama_result.json'
}
processed_records_ids = []
last_processed_ids = 0
with open(config['record_path'], 'r') as f1:
    records = [json.loads(line) for line in f1]
    for record in records:
        last_processed_ids = record['_id']
        if record['_id'] not in processed_records_ids:
            processed_records_ids.append(record['_id'])

with open(config['record_path'], 'a') as f0:
    with open(config['dataset_path'], 'r') as f:
        records = [json.loads(line) for line in f]
        # records = [records[1]]
        for record in records:
            if record['_id'] <= last_processed_ids:
                continue
            try:
                print(f"Processing {record['_id']}")
                #LLM 打分
                prompt_for_classifier = model.prompt_for_classifier(record["old"], record["review"], record["new"])
                classification = model.get_model_response(prompt_for_classifier)[1]
                # relevance_score = re.search(r'(\d+),', classification).group(1)
                # context_dependency_score = re.search(r'(\d+),', classification).group(2)
                relevance_score = re.search(r'"Relevance Score": (\d+),', classification).group(1)
                context_dependency_score = re.search(r'"Context Dependency Score": (\d+),', classification).group(1)
                record["classification"] = {"Relevance Score": int(relevance_score), "Context Dependency Score": int(context_dependency_score), "Response": classification}
                #process
                print(f"Classification: {classification}")
                agent = AgentRefiner(config, record)
                record = agent.process()
                f0.write(json.dumps(record, ensure_ascii=False) + '\n')
                print(f"")
            except Exception as e:
                print(f"Error processing {record['_id']}: {e}")
with open(config['result_path'], 'w') as f1:
    with open(config['record_path'], 'r') as f2:
        records = [json.loads(line) for line in f2]
        f1.write(json.dumps(records, ensure_ascii=False))