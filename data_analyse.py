import json
import model

# with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_with_llama_cr_new_trim4.json', 'r') as f:
# with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_with_llama_cr_new_trim2.json', 'r') as f:
with open('/mnt/ssd2/wangke/CR_data/dataset/dataset_all_3.json', 'r') as f:
    records = json.load(f)

    score = [[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0],],[0,[0,0,0,0]],[0,[0,0,0,0]]]
    score2 = [0,0,0,0]
    abort_analysis_result = {
        "case1:Unable to get the prompt_for_instruction result_json": 0,
        "case2:Unable to extract function name from the prompt_for_instruction result using regular expressions": 0,
        "case3:The function name has already existed":0,
        "case4:Unable to find the definition of the function name":0
    }
    num = 0
    ids = []
    for record in records:
        #方便查看结果
        record["code_diff"] = "Omit"
        record["context"] = "Omit"
        
        results = record['results']
        if not record["_id"] > 0 : continue
        # if record["_id"] > 0 : continue
        # if record["_id"] < -2312 or record["_id"] > 0: continue
        if len(results) == 0: continue
        score2[0] += record["gpt_bleu"]
        score2[1] += record["gpt_bleu_trim"]
        score2[2] += record["llama_bleu"]
        score2[3] += record["llama_bleu_trim"]

        turn = -1
        

        # if len(results) == 1: continue
        for result in results:
            # result_json = '\n'.join(result["result_json"])
            # if result_json.find("need more information?\": \"True") == -1: break

            abort_analysis = result.get("flag_for_context_change", None)
            if abort_analysis:
                abort_analysis_result[abort_analysis] += 1
            
            # if not result.get("new_code"): continue
            turn = result['turn'] - 1
            if True:
            # if result["bleu_trim"] > 50: 
                score[turn][0] += 1
                score[turn][1][0] += result["em"]
                score[turn][1][1] += result["em_trim"]
                score[turn][1][2] += result["bleu"]
                score[turn][1][3] += result["bleu_trim"]
            
            if turn == 1 and result["bleu_trim"] < results[0]["bleu_trim"]:
                num += 1
                if results[0]["bleu_trim"] - result["bleu_trim"] > 30:
                    ids.append(record["_id"])
            
            # if results[0]["bleu_trim"] > 50 and result["bleu_trim"] < 50:
            if results[0]["bleu_trim"] - result["bleu_trim"] > 30:
                print(f"id:{record['_id']};turn:{turn+1};bleu_trim:{result['bleu_trim']}")

            # if result_json.find("need more information?\": \"False") != -1:
            #     break
            
        
        if turn == -1: continue
        # result = results[-1]
        # for i in range(len(results), 6):
        result = results[turn]
        for i in range(turn+1, 6):
            # score[i][0] += 1
            score[i][1][0] += result["em"]
            score[i][1][1] += result["em_trim"]
            score[i][1][2] += result["bleu"]
            score[i][1][3] += result["bleu_trim"]

    print(f"num:{num}")    
    for i in range(6):
        count = score[0][0]
        if count != 0:
            print(f"turn:{i}; count:{score[i][0]}; em:{score[i][1][0]/count}; em_trim:{score[i][1][1]/count};  bleu:{score[i][1][2]/count}; bleu_trim:{score[i][1][3]/count}")
    count = len(records)

    for key, value in abort_analysis_result.items():
        print(f"{key}:{value}")
    # print(f"total count:{count}; gpt_bleu:{score2[0]/count}; gpt_bleu_trim:{score2[1]/count}; llama_bleu:{score2[2]/count}; llama_bleu_trim:{score2[3]/count}")
    
    # with open('/mnt/ssd2/wangke/CR_data/dataset/dataset_negative_30.json', 'w') as f1:
    #     records2 = [record for record in records if record["_id"] in ids]
    #     f1.write(json.dumps(records2, indent=4))
    # with open('/mnt/ssd2/wangke/CR_data/dataset/dataset_part.json', 'w') as f1:
    #     # records2 = [record for record in records if record["_id"] in ids]
    #     f1.write(json.dumps(records, indent=4))

# with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_test_with_llama_all.json', 'r') as f:
# # with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_with_llama_cr_new.json', 'r') as f:
#     records = json.load(f)
#     delete_ids = []
#     for record in records:
#         if record["_id"] == 2289:
#             pass
#         if not record.get("new"): continue
#         results = record['results']
#         end_line = record["old"].split('\n')[-1][1:]
#         for result in results:
            
#             result["new_code_groud_truth"] = record["new"].split('\n')
#             index = -1
#             if not result.get("new_code"):
#                 results.remove(result)
#                 continue
#             if result["turn"] == 1: continue
#             for i, line in enumerate(result["new_code"]):
#                 if line.strip() == end_line.strip():
#                     index = i
#             if index != -1:
#                 result["new_code"] = result["new_code"][:index+1]
#                 print(f"已在new_code中截取到{end_line}")
#                 # new_without_plus = model.remove_minus_or_plus(record['new'], '+')
#                 new = record['new']
#                 new_code = result["new_code"]
#                 # em, em_trim, bleu, bleu_trim = model.calc_em_and_bleu(('\n').join(new_code), new_without_plus)
#                 em, em_trim, bleu, bleu_trim = model.calc_em_and_bleu(new, ('\n').join(new_code))
#                 result["em"] = em
#                 result["em_trim"] = em_trim
#                 result["bleu"] = bleu
#                 result["bleu_trim"] = bleu_trim
#             else: 
#                 print(f"没有在new_code中找到{end_line}")
#                 # delete_ids.append(record["_id"])
#     # records = [record for record in records if record["_id"] not in delete_ids]

#     with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_with_llama_cr_new_trim4.json', 'w') as f1:
#         f1.write(json.dumps(records, indent=4))