import json
import traceback
config = {
    # "dataset_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/final_results/result_for_preprocessed_datasets.json",
    "dataset_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/final_results/result2.json",
    "tmp_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/tmp_result.json"
}
with open(config["dataset_path"], "r") as f:
    records = [json.loads(line) for line in f]
    print(f"len(records)={len(records)}")
    records = [record for record in records if record["new_added_identifiers_review_strict"] and record["new_added_identifiers_definition_strict"]]
    print(f"len(records)={len(records)}")
    # recall, precision, f1, em, em_trim, bleu, bleu_trim
    evaluation_results = {
        "Agent": [0, 0, 0]
    }
    Agent_results = {}
    for layer in range(1,5):
        Agent_results[f"layer{layer}"] = [0, 0, 0]
    for index, metric in enumerate(["Intention", "Guo2024", "Vallina", "With_In_File_context", "With_Cross_File_context"]):
        evaluation_results[metric] = []
        for i in range(10):
            evaluation_results[metric].append([0, 0, 0])
    records_len = len(records)
    records_to_analysis = []
    for record in records:
        try:
            evaluation_results["Agent"][0] += record["Evaluation_Results"]["recall"]
            evaluation_results["Agent"][1] += record["Evaluation_Results"]["precision"]
            evaluation_results["Agent"][2] += record["Evaluation_Results"]["f1_score"]
            max_len = len(record["names_of_relevance_context"])
            for layer in range(1,5):
                for index, metric in enumerate(["recall", "precision", "f1_score"]):
                    Agent_results[f"layer{layer}"][index] += record["names_of_relevance_context"][min(layer-1, max_len-1)]["evaluation_results"][metric]
            for ablation_index, llm in enumerate(["llama", "deepseek", "deepseek_r1"]):
                for index, metric in enumerate(["Intention", "Guo2024", "Vallina", "With_In_File_context", "With_Cross_File_context"]):
                    if not record["results"][index]["ablation_results"][ablation_index].get("Added_Identifie_Match",None):
                        record["results"][index]["ablation_results"][ablation_index]["Added_Identifie_Match"] = {
                            "recall" : 0,
                            "precision" : 0,
                            "f1_score" : 0
                        }
                    evaluation_results[metric][0][ablation_index] += record["results"][index]["ablation_results"][ablation_index]["Identifie_Match"]["recall"]
                    evaluation_results[metric][1][ablation_index] += record["results"][index]["ablation_results"][ablation_index]["Identifie_Match"]["precision"]
                    evaluation_results[metric][2][ablation_index] += record["results"][index]["ablation_results"][ablation_index]["Identifie_Match"]["f1_score"]
                    evaluation_results[metric][3][ablation_index] += record["results"][index]["ablation_results"][ablation_index]["Added_Identifie_Match"]["recall"]
                    evaluation_results[metric][4][ablation_index] += record["results"][index]["ablation_results"][ablation_index]["Added_Identifie_Match"]["precision"]
                    evaluation_results[metric][5][ablation_index] += record["results"][index]["ablation_results"][ablation_index]["Added_Identifie_Match"]["f1_score"]
                    evaluation_results[metric][6][ablation_index] += record["results"][index]["ablation_results"][ablation_index]["em"]
                    evaluation_results[metric][7][ablation_index] += record["results"][index]["ablation_results"][ablation_index]["em_trim"]
                    evaluation_results[metric][8][ablation_index] += record["results"][index]["ablation_results"][ablation_index]["bleu"]
                    evaluation_results[metric][9][ablation_index] += record["results"][index]["ablation_results"][ablation_index]["bleu_trim"]
                # if record["results"][0]["ablation_results"][ablation_index]["Added_Identifie_Match"]["recall"] > record["results"][2]["ablation_results"][ablation_index]["Added_Identifie_Match"]["recall"]:
                #     records_to_analysis.append(record)
                if record["results"][3]["ablation_results"][ablation_index]["Added_Identifie_Match"]["recall"] > 0.79:
                    records_to_analysis.append(record)
        except Exception as e:
            print(f"Error processing record {record['_id']}: {e}")
            traceback.print_exc()
            records_len -= 1
    #遍历evaluation_results的每一个ablation的每一个metrics，除以总的数量
    for ablation in evaluation_results:
        if ablation == "Agent":
            for i in range(3):
                evaluation_results[ablation][i] /= records_len
        else:
            for i in range(10):
                for j in range(3):
                    evaluation_results[ablation][i][j] /= records_len
    for layer in range(1,5):
        for i in range(3):
            Agent_results[f"layer{layer}"][i] /= records_len
    
    #输出结果
    print(f"Agent Capability                                  : recall={evaluation_results['Agent'][0]}, precision={evaluation_results['Agent'][1]}, f1={evaluation_results['Agent'][2]}")
    for layer in range(1,5):
        print(f"Layer{layer} Capability                            : recall={Agent_results[f'layer{layer}'][0]}, precision={Agent_results[f'layer{layer}'][1]}, f1={Agent_results[f'layer{layer}'][2]}")
    for ablation_index, llm in enumerate(["llama", "deepseek", "deepseek_r1"]):
        print(f"评估的大模型：{llm}")
        print(f"Identifier Match")
        print(f"Intention Refine Result                           : recall={evaluation_results['Intention'][0][ablation_index]}, precision={evaluation_results['Intention'][1][ablation_index]}, f1={evaluation_results['Intention'][2][ablation_index]}")
        print(f"Guo2024 Refine Result                             : recall={evaluation_results['Guo2024'][0][ablation_index]}, precision={evaluation_results['Guo2024'][1][ablation_index]}, f1={evaluation_results['Guo2024'][2][ablation_index]}")
        print(f"Vallina Refine Result                             : recall={evaluation_results['Vallina'][0][ablation_index]}, precision={evaluation_results['Vallina'][1][ablation_index]}, f1={evaluation_results['Vallina'][2][ablation_index]}")
        print(f"Vallina Refine Result with In-File Context        : recall={evaluation_results['With_In_File_context'][0][ablation_index]}, precision={evaluation_results['With_In_File_context'][1][ablation_index]}, f1={evaluation_results['With_In_File_context'][2][ablation_index]}")
        print(f"Vallina Refine Result with Cross-File Context     : recall={evaluation_results['With_Cross_File_context'][0][ablation_index]}, precision={evaluation_results['With_Cross_File_context'][1][ablation_index]}, f1={evaluation_results['With_Cross_File_context'][2][ablation_index]}")
        print(f"Added Identifier Match")
        print(f"Intention Refine Result                           : recall={evaluation_results['Intention'][3][ablation_index]}, precision={evaluation_results['Intention'][4][ablation_index]}, f1={evaluation_results['Intention'][5][ablation_index]}")
        print(f"Guo2024 Refine Result                             : recall={evaluation_results['Guo2024'][3][ablation_index]}, precision={evaluation_results['Guo2024'][4][ablation_index]}, f1={evaluation_results['Guo2024'][5][ablation_index]}")
        print(f"Vallina Refine Result                             : recall={evaluation_results['Vallina'][3][ablation_index]}, precision={evaluation_results['Vallina'][4][ablation_index]}, f1={evaluation_results['Vallina'][5][ablation_index]}")
        print(f"Vallina Refine Result with In-File Context        : recall={evaluation_results['With_In_File_context'][3][ablation_index]}, precision={evaluation_results['With_In_File_context'][4][ablation_index]}, f1={evaluation_results['With_In_File_context'][5][ablation_index]}")
        print(f"Vallina Refine Result with Cross-File Context     : recall={evaluation_results['With_Cross_File_context'][3][ablation_index]}, precision={evaluation_results['With_Cross_File_context'][4][ablation_index]}, f1={evaluation_results['With_Cross_File_context'][5][ablation_index]}")
        print(f"EM and BLEU")
        print(f"Intention Refine Result                           : em={evaluation_results['Intention'][6][ablation_index]}, em_trim={evaluation_results['Intention'][7][ablation_index]}, bleu={evaluation_results['Intention'][8][ablation_index]}, bleu_trim={evaluation_results['Intention'][9][ablation_index]}")
        print(f"Guo2024 Refine Result                             : em={evaluation_results['Guo2024'][6][ablation_index]}, em_trim={evaluation_results['Guo2024'][7][ablation_index]}, bleu={evaluation_results['Guo2024'][8][ablation_index]}, bleu_trim={evaluation_results['Guo2024'][9][ablation_index]}")
        print(f"Vallina Refine Result                             : em={evaluation_results['Vallina'][6][ablation_index]}, em_trim={evaluation_results['Vallina'][7][ablation_index]}, bleu={evaluation_results['Vallina'][8][ablation_index]}, bleu_trim={evaluation_results['Vallina'][9][ablation_index]}")
        print(f"Vallina Refine Result with In-File Context        : em={evaluation_results['With_In_File_context'][6][ablation_index]}, em_trim={evaluation_results['With_In_File_context'][7][ablation_index]}, bleu={evaluation_results['With_In_File_context'][8][ablation_index]}, bleu_trim={evaluation_results['With_In_File_context'][9][ablation_index]}")
        print(f"Vallina Refine Result with Cross-File Context     : em={evaluation_results['With_Cross_File_context'][6][ablation_index]}, em_trim={evaluation_results['With_Cross_File_context'][7][ablation_index]}, bleu={evaluation_results['With_Cross_File_context'][8][ablation_index]}, bleu_trim={evaluation_results['With_Cross_File_context'][9][ablation_index]}")

with open(config["tmp_path"], "w") as f:
    json.dump(records_to_analysis, f, indent=4)