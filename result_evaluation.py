import json
import traceback

# 配置
config = {
    # "dataset_path": "/data/DataLACP/wangke/recorebench/result/3.0/rq12.json",
    # "dataset_path": "/data/DataLACP/wangke/recorebench/result/2.0/rq2_0.json",
    # "dataset_path": "/data/DataLACP/wangke/recorebench/result/5.0/rq12_ordered.json",
    # "dataset_path": "/data/DataLACP/wangke/recorebench/result/5.0/rq12_general.json",
    # "dataset_path": "/data/DataLACP/wangke/recorebench/result/5.0/rq12_web.json",
    # "dataset_path": "/data/DataLACP/wangke/recorebench/result/5.0/rq12_history.json",
    "dataset_path": "/data/DataLACP/wangke/recorebench/result/5.0/rq12_py.json",
    # "dataset_path": "/data/DataLACP/wangke/recorebench/result/5.0/rq12_java.json",
    # "dataset_path": "/data/DataLACP/wangke/recorebench/result/5.0/rq12_js.json",
    
    "tmp_path": "/data/DataLACP/wangke/recorebench/result/dataset/tmp_result.json",
    "llms": ["llama", "deepseek", "deepseek-r1", "gpt-4o"],
    "metrics": [
        "simple_prompt",
        "simple_prompt_with_self_generated",
        "simple_prompt_with_rag",
        "simple_prompt_with_in_file_context",
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
    def format_value(value, is_percentage=True):
        return f"{value * 100:.2f}" if is_percentage else f"{value:.2f}"

    def format_line(metric, label, vals, ablation_index):
        recall = format_value(vals[0][ablation_index])
        precision = format_value(vals[1][ablation_index])
        f1 = format_value(vals[2][ablation_index])
        return f"{metric.ljust(44)}: recall={recall}, precision={precision}, f1={f1}"

    def format_bleu_line(metric, label, vals, ablation_index):
        em = format_value(vals[6][ablation_index])
        em_trim = format_value(vals[7][ablation_index])
        bleu = format_value(vals[8][ablation_index], is_percentage=False)
        bleu_trim = format_value(vals[9][ablation_index], is_percentage=False)
        return f"{metric.ljust(44)}: em={em}, em_trim={em_trim}, bleu={bleu}, bleu_trim={bleu_trim}"

    for metric in metrics:
        for i in range(10):
            for j in range(len(llms)):
                evaluation_results[metric][i][j] /= records_len

    for ablation_index, llm in enumerate(llms):
        metrics = ["simple_prompt", "simple_prompt_with_in_file_context", "simple_prompt_with_cross_file_context"]#只打印这三个指标
        print(f"\n评估的大模型：{llm}\nIdentifier Match")
        for metric in metrics:
            print(format_line(metric, "Identifier Match", evaluation_results[metric], ablation_index))

        print("Added Identifier Match")
        for metric in metrics:
            offset = 3  # index offset for added match
            added_vals = evaluation_results[metric][offset:offset + 3] + evaluation_results[metric][6:]
            print(format_line(metric, "Added Identifier Match", added_vals, ablation_index))

        # print("EM and BLEU")
        # for metric in metrics:
        #     print(format_bleu_line(metric, "EM and BLEU", evaluation_results[metric], ablation_index))

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
