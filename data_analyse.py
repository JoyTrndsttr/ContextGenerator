import json

with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_with_llama_all_trim.json', 'r') as f:
    records = json.load(f)

    score = [[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]],[0,[0,0,0,0]]]
    score2 = [0,0,0,0]
    
    for record in records:
        results = record['results']
        score2[0] += record["gpt_bleu"]
        score2[1] += record["gpt_bleu_trim"]
        score2[2] += record["llama_bleu"]
        score2[3] += record["llama_bleu_trim"]

        # if len(results) == 1: continue
        for result in results:
            # if result["bleu_trim"] < 0: continue
            turn = result['turn'] - 1
            score[turn][0] += 1
            score[turn][1][0] += result["em"]
            score[turn][1][1] += result["em_trim"]
            score[turn][1][2] += result["bleu"]
            score[turn][1][3] += result["bleu_trim"]
            if result["bleu_trim"] < 20:
                print(f"id:{record['_id']};turn:{turn+1};bleu_trim:{result['bleu_trim']}")
        for i in range(len(results), 4):
            score[i][0] += 1
            score[i][1][0] += result["em"]
            score[i][1][1] += result["em_trim"]
            score[i][1][2] += result["bleu"]
            score[i][1][3] += result["bleu_trim"]

        
    for i in range(5):
        count = score[i][0]
        if count != 0:
            print(f"turn:{i+1}; count:{count}; em:{score[i][1][0]/count}; em_trim:{score[i][1][1]/count};  bleu:{score[i][1][2]/count}; bleu_trim:{score[i][1][3]/count}")
    count = len(records)
    print(f"total count:{count}; gpt_bleu:{score2[0]/count}; gpt_bleu_trim:{score2[1]/count}; llama_bleu:{score2[2]/count}; llama_bleu_trim:{score2[3]/count}")
    

# with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_test_with_llama_all.json', 'r') as f:
#     records = json.load(f)
#     for record in records:
#         if record["_id"] == 2289:
#             pass
#         results = record['results']
#         end_line = record["old"].split('\n')[-1][1:]
#         for result in results:
            
#             result["new_code_groud_truth"] = record["new"].split('\n')
#             index = -1
#             if not result.get("new_code"):
#                 results.remove(result)
#                 continue
#             for i, line in enumerate(result["new_code"]):
#                 if line.strip() == end_line.strip():
#                     index = i
#             if index != -1:
#                 result["new_code"] = result["new_code"][:index+1]
#                 print(f"已在new_code中截取到{end_line}")
#             else: print(f"没有在new_code中找到{end_line}")

            


#     with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_with_llama_all_trim.json', 'w') as f1:
#         f1.write(json.dumps(records, indent=4))