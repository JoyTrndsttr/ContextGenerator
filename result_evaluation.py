import json
config = {
    "dataset_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/final_results/result_for_datasets_human_filtered.json"
}
with open(config["dataset_path"], "r") as f:
    records = [json.loads(line) for line in f]
    # records = [record for record in records if record["review"]==record["original_review"]]
    print(f"len(records)={len(records)}")
    # recall, precision, f1, em, em_trim, bleu, bleu_trim
    evaluation_results = {
        "Agent": [0, 0, 0],
        "Vallina": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "With_In_File_context": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "With_Cross_File_context": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    }
    len = len(records)
    for record in records:
        try:
            evaluation_results["Agent"][0] += record["Evaluation_Results"]["recall"]
            evaluation_results["Agent"][1] += record["Evaluation_Results"]["precision"]
            evaluation_results["Agent"][2] += record["Evaluation_Results"]["f1_score"]
            for index, metric in enumerate(["Vallina", "With_In_File_context", "With_Cross_File_context"]):
                evaluation_results[metric][0] += record["results"][index]["ablation_results"][0]["Identifie_Match"]["recall"]
                evaluation_results[metric][1] += record["results"][index]["ablation_results"][0]["Identifie_Match"]["precision"]
                evaluation_results[metric][2] += record["results"][index]["ablation_results"][0]["Identifie_Match"]["f1_score"]
                evaluation_results[metric][3] += record["results"][index]["ablation_results"][0]["Added_Identifie_Match"]["recall"]
                evaluation_results[metric][4] += record["results"][index]["ablation_results"][0]["Added_Identifie_Match"]["precision"]
                evaluation_results[metric][5] += record["results"][index]["ablation_results"][0]["Added_Identifie_Match"]["f1_score"]
                evaluation_results[metric][6] += record["results"][index]["ablation_results"][0]["em"]
                evaluation_results[metric][7] += record["results"][index]["ablation_results"][0]["em_trim"]
                evaluation_results[metric][8] += record["results"][index]["ablation_results"][0]["bleu"]
                evaluation_results[metric][9] += record["results"][index]["ablation_results"][0]["bleu_trim"]
        except:
            print(record["_id"])
            len -= 1
    #遍历evaluation_results的每一个ablation的每一个metrics，除以总的数量
    for ablation in evaluation_results:
        if ablation == "Agent":
            for i in range(3):
                evaluation_results[ablation][i] /= len
        else:
            for i in range(10):
                evaluation_results[ablation][i] /= len
    
    #输出结果
    print(f"Agent Capability                                  : recall={evaluation_results['Agent'][0]}, precision={evaluation_results['Agent'][1]}, f1={evaluation_results['Agent'][2]}")
    print(f"Vallina Refine Result                             : recall={evaluation_results['Vallina'][0]}, precision={evaluation_results['Vallina'][1]}, f1={evaluation_results['Vallina'][2]}")
    print(f"Vallina Refine Result with In-File Context        : recall={evaluation_results['With_In_File_context'][0]}, precision={evaluation_results['With_In_File_context'][1]}, f1={evaluation_results['With_In_File_context'][2]}")
    print(f"Vallina Refine Result with Cross-File Context     : recall={evaluation_results['With_Cross_File_context'][0]}, precision={evaluation_results['With_Cross_File_context'][1]}, f1={evaluation_results['With_Cross_File_context'][2]}")
    print(f"Vallina Refine Result                             : recall={evaluation_results['Vallina'][3]}, precision={evaluation_results['Vallina'][4]}, f1={evaluation_results['Vallina'][5]}")
    print(f"Vallina Refine Result with In-File Context        : recall={evaluation_results['With_In_File_context'][3]}, precision={evaluation_results['With_In_File_context'][4]}, f1={evaluation_results['With_In_File_context'][5]}")
    print(f"Vallina Refine Result with Cross-File Context     : recall={evaluation_results['With_Cross_File_context'][3]}, precision={evaluation_results['With_Cross_File_context'][4]}, f1={evaluation_results['With_Cross_File_context'][5]}")
    print(f"Vallina Refine Result                             : em={evaluation_results['Vallina'][6]}, em_trim={evaluation_results['Vallina'][7]}, bleu={evaluation_results['Vallina'][8]}, bleu_trim={evaluation_results['Vallina'][9]}")
    print(f"Vallina Refine Result with In-File Context        : em={evaluation_results['With_In_File_context'][6]}, em_trim={evaluation_results['With_In_File_context'][7]}, bleu={evaluation_results['With_In_File_context'][8]}, bleu_trim={evaluation_results['With_In_File_context'][9]}")
    print(f"Vallina Refine Result with Cross-File Context     : em={evaluation_results['With_Cross_File_context'][6]}, em_trim={evaluation_results['With_Cross_File_context'][7]}, bleu={evaluation_results['With_Cross_File_context'][8]}, bleu_trim={evaluation_results['With_Cross_File_context'][9]}")

