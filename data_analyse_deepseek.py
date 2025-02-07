import json
import model

# with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_with_llama_cr_new_trim4.json', 'r') as f:
# with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_with_llama_cr_new_trim2.json', 'r') as f:
with open('//mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_deepseek.json', 'r') as f:
# with open('/mnt/ssd2/wangke/CR_data/dataset/map_result/tmp.json', 'r') as f:
    records = []
    for line in f:
        record = json.loads(line.strip())
        records.append(record)
    # with open('//mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_all_deepseek.json', 'w') as f2:
    #     json.dump(records, f2, indent=4)
    

    score = [[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0],],[0,[0,0,0,0]],[0,[0,0,0,0]]]
    # score2 = [0,0,0,0]
    # abort_analysis_result = {
    #     "case1:Unable to get the prompt_for_instruction result_json": 0,
    #     "case2:Unable to extract function name from the prompt_for_instruction result using regular expressions": 0,
    #     "case3:The function name has already existed":0,
    #     "case4:Unable to find the definition of the function name":0
    # }
    num = 0
    ids = []
    for record in records:
        
        results = record['results']
    #     # if not record["_id"] > 0 : continue
    #     # if record["_id"] > 0 : continue
    #     # if record["_id"] < -2312 or record["_id"] > 0: continue
    #     if len(results) == 0: continue
    #     score2[0] += record["gpt_bleu"]
    #     score2[1] += record["gpt_bleu_trim"]
    #     score2[2] += record["llama_bleu"]
    #     score2[3] += record["llama_bleu_trim"]

        turn = -1

        # new_code_flag = True
        # for result in results:
        #     if not result.get("new_code", None):
        #         new_code_flag = False
        # if not new_code_flag: 
        #     print(f"id:{record['id']};new_code_flag:{new_code_flag}")
        #     continue
        

    #     # if len(results) == 1: continue
        for turn,result in enumerate(results):
    #         # result_json = '\n'.join(result["result_json"])
    #         # if result_json.find("need more information?\": \"True") == -1: break

    #         abort_analysis = result.get("flag_for_context_change", None)
    #         if abort_analysis:
    #             abort_analysis_result[abort_analysis] += 1
            
    #         if not result.get("new_code"): continue
            # turn = result['turn'] - 1
            if True:
            # if result["bleu_trim"] > 50: 
                score[turn][0] += 1
                score[turn][1][0] += result["em"]
                score[turn][1][1] += result["em_trim"]
                score[turn][1][2] += result["bleu"]
                score[turn][1][3] += result["bleu_trim"]
            
    #         if turn == 1 and result["bleu_trim"] < results[0]["bleu_trim"]:
    #             num += 1
    #             if results[0]["bleu_trim"] - result["bleu_trim"] > 30:
    #                 ids.append(record["_id"])
            
    #         # if results[0]["bleu_trim"] > 50 and result["bleu_trim"] < 50:
    #         if results[0]["bleu_trim"] - result["bleu_trim"] > 30:
    #             print(f"id:{record['_id']};turn:{turn+1};bleu_trim:{result['bleu_trim']}")

    #         # if result_json.find("need more information?\": \"False") != -1:
    #         #     break
            
        
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

    # print(f"num:{num}")    
    for i in range(6):
        count = score[0][0]
        if count != 0:
            print(f"turn:{i+1}; count:{score[i][0]}; em:{score[i][1][0]/count}; em_trim:{score[i][1][1]/count};  bleu:{score[i][1][2]/count}; bleu_trim:{score[i][1][3]/count}")
    count = len(records)
    # for key, value in abort_analysis_result.items():
    #     print(f"{key}:{value}")
    