import json
import model

# with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_with_llama_cr_new_trim4.json', 'r') as f:
# with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_with_llama_cr_new_trim2.json', 'r') as f:
# with open('/mnt/ssd2/wangke/CR_data/dataset/dataset_part.json', 'r') as f:

# with open('/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_llama.json', 'r') as f:
# with open('/mnt/ssd2/wangke/dataset/cr_data/dataset_sorted_llama_instructed_processed.json', 'r') as f:
# with open('/mnt/ssd2/wangke/dataset/cr_data/dataset_sorted_llama_instructed_map_deepseek_processed.json', 'r') as f:
#     records = json.load(f)
# with open('/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/CR_and_CRN.json', 'r') as f:
with open('/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/CR_and_CRN_estimated.json', 'r') as f:
# with open('/mnt/ssd2/wangke/dataset/AgentRefiner/map_result.json', 'r') as f:
    records = [json.loads(line) for line in f]
    records = [record for record in records if record["repo_context_dependency_estimation"]["Additional_context_required"]=="1"]
    
# with open('/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_ablation_deepseek.json', 'r') as f:
# with open('/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_ablation_deepseek2.json', 'r') as f:
# # with open('/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_ablation_deepseek_default.json', 'r') as f:
# # with open('/mnt/ssd2/wangke/CR_data/dataset/deepseek/ablation_results.jsonl', 'r') as f:        
#     records = []
#     for line in f:
#         record = json.loads(line.strip())
#         records.append(record)

    # for record in records:
    #     result = record['results'][0]
    #     ablation_results = result.get("ablation_results", [])
    #     #替换第一个和第三个
    #     tmp_ablation_results = ablation_results[2]
    #     ablation_results[2] = ablation_results[0]
    #     ablation_results[2]["ablation_info"] = "Code_cut_precise"
    #     ablation_results[0] = tmp_ablation_results
    #     ablation_results[0]["ablation_info"] = "Summary_cut_precise"
            

    # score = [[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0],],[0,[0,0,0,0]],[0,[0,0,0,0]]]
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
        if len(results) == 1: continue

        model_score[0] += record["model_em"]
        model_score[1] += record["model_em_trim"]
        model_score[2] += record["model_bleu"]
        model_score[3] += record["model_bleu_trim"]
        gpt_score[0] += record["gpt_em"]
        gpt_score[1] += record["gpt_em_trim"]
        gpt_score[2] += record["gpt_bleu"]
        gpt_score[3] += record["gpt_bleu_trim"]

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
            ablation_results_len = len(result.get("ablation_results", []))
            
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
                ids.append(record["_id"])
            else: equal += 1
            # if results[0]["ablation_results"][1]["bleu_trim"] - results[1]["ablation_results"][1]["bleu_trim"] > 30 and results[1]["ablation_results"][1]["bleu_trim"] != 0:
            # if results[1]["ablation_results"][0]["em"] - results[0]["ablation_results"][0]["em"] == -1:
            #     ids.append(record["_id"])
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
    
    count = score[0][0]
    print(f"model_em:{model_score[0]/count}, model_em_trim:{model_score[1]/count}, model_bleu:{model_score[2]/count}, model_bleu_trim:{model_score[3]/count}")
    print(f"gpt_em:{gpt_score[0]/count}, gpt_em_trim:{gpt_score[1]/count}, gpt_bleu:{gpt_score[2]/count}, gpt_bleu_trim:{gpt_score[3]/count}")

    # with open('/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_negative_deepseek.json', 'w') as f:
    with open('/mnt/ssd2/wangke/dataset/cr_data/case_study.json', 'w') as f:
        print(f"len(ids):{len(ids)}")
        records = [record for record in records if record["_id"] in ids]
        json.dump(records, f, indent=4)