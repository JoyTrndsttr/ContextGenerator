import json
import traceback

# 配置
config = {
    "dataset_path": "/data/DataLACP/wangke/recorebench/result/1.0/rq1_0.json",
    "tmp_path": "/data/DataLACP/wangke/recorebench/result/dataset/tmp_result.json",
    "llms": ["llama", "deepseek"],
    "metrics": [
        "simple_prompt",
        "simple_prompt_with_self_generated",
        "simple_prompt_with_rag",
        "simple_prompt_with_cross_file_context"
    ],
    "fields": [
        "Identifie_Match",
        "Added_Identifie_Match",
        "em",
        "em_trim",
        "bleu",
        "bleu_trim"
    ]
}

def initialize_results(metrics, llms, fields):
    return {
        metric: [[0.0 for _ in llms] for _ in range(10)]
        for metric in metrics
    }

def safe_get(d, key, default):
    return d.get(key, default) if isinstance(d, dict) else default

def process_record(record, evaluation_results, llms, metrics):
    for ablation_index, _ in enumerate(llms):
        for metric_index, metric in enumerate(metrics):
            ablation_data = record["results"][metric_index]["ablation_results"][ablation_index]
            added_match = safe_get(ablation_data, "Added_Identifie_Match", {"recall": 0, "precision": 0, "f1_score": 0})
            ablation_data["Added_Identifie_Match"] = added_match

            evaluation_results[metric][0][ablation_index] += ablation_data["Identifie_Match"]["recall"]
            evaluation_results[metric][1][ablation_index] += ablation_data["Identifie_Match"]["precision"]
            evaluation_results[metric][2][ablation_index] += ablation_data["Identifie_Match"]["f1_score"]
            evaluation_results[metric][3][ablation_index] += added_match["recall"]
            evaluation_results[metric][4][ablation_index] += added_match["precision"]
            evaluation_results[metric][5][ablation_index] += added_match["f1_score"]
            evaluation_results[metric][6][ablation_index] += ablation_data.get("em", 0)
            evaluation_results[metric][7][ablation_index] += ablation_data.get("em_trim", 0)
            evaluation_results[metric][8][ablation_index] += ablation_data.get("bleu", 0)
            evaluation_results[metric][9][ablation_index] += ablation_data.get("bleu_trim", 0)

def print_results(evaluation_results, llms, metrics, records_len):
    for metric in metrics:
        for i in range(10):
            for j in range(len(llms)):
                evaluation_results[metric][i][j] /= records_len

    for ablation_index, llm in enumerate(llms):
        print(f"评估的大模型：{llm}\nIdentifier Match")
        for metric in metrics:
            print(f"{metric} Refine Result : recall={evaluation_results[metric][0][ablation_index]}, "
                  f"precision={evaluation_results[metric][1][ablation_index]}, "
                  f"f1={evaluation_results[metric][2][ablation_index]}")
        print("Added Identifier Match")
        for metric in metrics:
            print(f"{metric} Refine Result : recall={evaluation_results[metric][3][ablation_index]}, "
                  f"precision={evaluation_results[metric][4][ablation_index]}, "
                  f"f1={evaluation_results[metric][5][ablation_index]}")
        print("EM and BLEU")
        for metric in metrics:
            print(f"{metric} Refine Result : em={evaluation_results[metric][6][ablation_index]}, "
                  f"em_trim={evaluation_results[metric][7][ablation_index]}, "
                  f"bleu={evaluation_results[metric][8][ablation_index]}, "
                  f"bleu_trim={evaluation_results[metric][9][ablation_index]}")

# 主逻辑
with open(config["dataset_path"], "r") as f:
    records = [json.loads(line) for line in f]
print(f"len(records)={len(records)}")

evaluation_results = initialize_results(config["metrics"], config["llms"], config["fields"])
records_to_analysis = []
records_len = len(records)

for record in records:
    try:
        process_record(record, evaluation_results, config["llms"], config["metrics"])
    except Exception as e:
        print(f"Error processing record {record.get('_id', 'unknown')}: {e}")
        traceback.print_exc()
        records_len -= 1

print_results(evaluation_results, config["llms"], config["metrics"], records_len)

# with open(config["tmp_path"], "w") as f:
#     json.dump(records_to_analysis, f, indent=2)
