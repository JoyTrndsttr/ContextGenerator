import json
import model
config = {
    "dataset_path": "/mnt/ssd2/wangke/dataset/datasets.json",
    "output_path": '/mnt/ssd2/wangke/dataset/map_result/',
    "record_path": '/mnt/ssd2/wangke/dataset/map_result/llama_map.json',
    "result_path": '/mnt/ssd2/wangke/dataset/map_result/llama_result.json',
    "analysis_path": '/mnt/ssd2/wangke/dataset/map_result/llama_analysis.json'
}
threshold = {
    "relevance": 10,
    "context_dependency": 10
}

records_to_analysis = []
with open(config["record_path"], 'r') as f:
    records = [json.loads(line) for line in f]
    score = []
    model_score = [0,0,0,0]
    gpt_score = [0,0,0,0]
    for i in range(6):
        turn_result = []
        turn_result.append(0)
        for i in range(8):
            turn_result.append([0,0,0,0])
        score.append(turn_result)
    abort_analysis_result = {
        "case1:Unable to get the prompt_for_instruction result_json": 0,
        "case2:Unable to extract function name from the prompt_for_instruction result using regular expressions": 0,
        "case3:The function name has already existed":0,
        "case4:Unable to find the definition of the function name":0,
        "case5:No need to check more information":0
    }
    ablation_info = [
        "Summary_cut_precise",
        "Summary_uncut_precise",
        "Code_cut_precise",
        "Code_uncut_precise",
        "Summary_cut_default",
        "Summary_uncut_default",
        "Code_cut_default",
        "Code_uncut_default"
    ]
    equal, better, worse = 0, 0, 0
    total_new_code, fail_new_code = 0, 0
    ids = []
    for record in records:
        

        results = record['results']
        if not record.get("id", None): record["id"] = record["_id"]
        # if not record["id"] > 0 : continue
        # if record["id"] > 0 : continue
        if len(results) == 0: continue
        # if len(results) == 1: continue

        turn = -1
        ablation_length = len(results[0].get("ablation_results", []))
        
        # new_code_flag = True
        # for result in results:
        #     for ablation_result in result.get("ablation_results", []):
        #         if not ablation_result.get("new_code", None) and not ablation_result.get("new_code_clipped", None):
        #             new_code_flag = False
        # if not new_code_flag: 
        #     # print(f"id:{record['_id']};new_code_flag:{new_code_flag}")
        #     print(f"id:{record['id']};new_code_flag:{new_code_flag}")
        #     continue

        relevance_score, context_dependency_score = record["classification"]["Relevance Score"], record["classification"]["Context Dependency Score"]
        if relevance_score < threshold["relevance"] and context_dependency_score < threshold["context_dependency"]:
            continue
        
        for result in results:
            for ablation_result in result.get("ablation_results", []):
                total_new_code += 1
                if not ablation_result.get("new_code", None):
                    fail_new_code += 1

        # if len(results) == 1: continue
        for result in results:
            # result_json = '\n'.join(result["result_json"])
            # if result_json.find("need more information?\": \"True") == -1: break

            abort_analysis = result.get("flag_for_context_change", None)
            if abort_analysis:
                abort_analysis_result[abort_analysis] += 1
            
            # if not result.get("new_code"): continue
            turn = result['turn'] - 1
            
            score[turn][0] += 1
            # ablation_results_len = len(result.get("ablation_results", []))
            # for i, ablation_result in enumerate(result.get("ablation_results", [])):
            #     if i in [0,2,4,6]:
            #         if result["ablation_results"][i]["bleu"] < result["ablation_results"][i+1]["bleu"]:
            #             result["ablation_results"][i] = result["ablation_results"][i+1]
            # for i, ablation_result in enumerate(result.get("ablation_results", [])):
            #     if i in [1,3,5,7] and not result["ablation_results"][i].get("new_code"):
            #         result["ablation_results"][i] = result["ablation_results"][i-1]
            for i, ablation_result in enumerate(result.get("ablation_results", [])):
                if True:
                # if result["bleu_trim"] > 50: 
                    score[turn][i+1][0] += result["ablation_results"][i]["em"]
                    score[turn][i+1][1] += result["ablation_results"][i]["em_trim"]
                    score[turn][i+1][2] += result["ablation_results"][i]["bleu"]
                    score[turn][i+1][3] += result["ablation_results"][i]["bleu_trim"]

        
        if turn == -1: continue
        # result = results[-1]
        # for i in range(len(results), 6):
        for j in range(ablation_length):
            result = results[turn]
            for i in range(turn+1, 6):
                # score[i][0] += 1
                score[i][j+1][0] += result["ablation_results"][j]["em"]
                score[i][j+1][1] += result["ablation_results"][j]["em_trim"]
                score[i][j+1][2] += result["ablation_results"][j]["bleu"]
                score[i][j+1][3] += result["ablation_results"][j]["bleu_trim"]

        if len(results) > 1:
            if results[1]["ablation_results"][0]["bleu_trim"] > results[0]["ablation_results"][0]["bleu_trim"]:
                better += 1
            elif results[1]["ablation_results"][0]["bleu_trim"] < results[0]["ablation_results"][0]["bleu_trim"]:
                worse += 1
            else: equal += 1
            # if results[0]["ablation_results"][1]["bleu_trim"] - results[1]["ablation_results"][1]["bleu_trim"] > 30 and results[1]["ablation_results"][1]["bleu_trim"] != 0:
            if results[1]["ablation_results"][0]["em"] - results[0]["ablation_results"][0]["em"] == 1:
                records_to_analysis.append(record)
    total = better + worse + equal
    print("new code format analysis:")
    print(f"total_new_code:{total_new_code}, fail_new_code:{fail_new_code}, {fail_new_code/total_new_code}")
    print("bleu_trim comparison:")
    # print(f"better:{better}, {better/total}")
    # print(f"worse:{worse}, {worse/total}")
    # print(f"equal:{equal}, {equal/total}")
    for j in range(ablation_length):
        print(f"{ablation_info[j]};")
        for i in range(6):
            count = score[0][0]
            if count != 0:
                print(f"turn:{i}; count:{score[i][0]}; em:{score[i][j+1][0]/count}; em_trim:{score[i][j+1][1]/count};  bleu:{score[i][j+1][2]/count}; bleu_trim:{score[i][j+1][3]/count}")
    count = len(records)

    for key, value in abort_analysis_result.items():
        print(f"{key}:{value}")

with open(config["analysis_path"], 'w') as f1:
    json.dump(records_to_analysis, f1, indent=4)