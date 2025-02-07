from ContextGenerators.getContextGenerators import LanguageContextGenerator
import getProjectCommitState
import logging
import ErrorProcess
import json
import model
import re
import traceback
# import concurrent.futures
import multiprocessing
import pathos.multiprocessing as mp
# from pathos.multiprocessing import ProcessingPool as Pool

# import functools

# Setting up logging
# logging.basicConfig(filename='log.txt', level=logging.ERROR, format='%(asctime)s:%(levelname)s:%(message)s')

# 主函数
def main(_id):
    # ids = ErrorProcess.error_ids2
    # with open('/mnt/ssd2/wangke/CR_data/dataset/dataset_all_5.json', 'w') as f0:
    with open('/mnt/ssd2/wangke/CR_data/dataset/test.json', 'w') as f0:
        f0.write('[\n')
        first_record = True
        with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python_all.json', 'r') as f:
            records = json.load(f)
            new_records = []
            for record in records:
                try:
                    # if not record['_id'] > 0 : continue
                    # if not record['_id'] == _id: continue
                    if record['_id']  > -5426 and record['_id'] <= 0 : continue
                    id = record['_id']
                    print(f'processing: {id}')
                    old_without_minus = model.remove_prefix(record['old'])
                    new_without_plus = model.remove_prefix(record['new'])
                    new = record['new']

                    # 获取仓库在commit提交前的状态
                    attempt = 0
                    while attempt < 1:
                        try:
                            successful_checkout = getProjectCommitState.main(id)
                            if successful_checkout:
                                break
                        except Exception as e:
                            attempt += 1
                            print(f'Error processing ID {id}: {e}')
                            if attempt == 1 :
                                logging.error(f'Error processing ID {id}: {e}', exc_info=True)  # Log error with stack trace
                                raise Exception(f'获取仓库在commit提交前的状态失败')
                    
                    #ReAct框架 
                    turn, flag_for_context_change, reason_for_name_selection = 0, True, ""
                    
                    languageContextGenerator = LanguageContextGenerator(id)
                    if not languageContextGenerator: return None
                    contextGenerator = languageContextGenerator.context_generator
                    review_info = languageContextGenerator.comment

                    calls = [] #元组格式，（调用的函数，被调用的函数，被调用函数的实现）
                    results = [] #存储每一个turn的结果
                    name = "" #存储要检索的函数名
                    name_list = [] #存储所有函数名

                    while turn < 6 and flag_for_context_change:
                        turn += 1
                        print(f"turn {turn}")
                        if name: contextGenerator.updateSource(name)
                        definitions = contextGenerator.getContext()
                        result = {"turn": turn, "result_json": "", "prompt_for_instruction": "","flag_for_context_change": "",  "ablation_results": []}
                        
                        max_attempts = 3
                        # 第二步：根据context、old_code和review生成new_code，并评估结果（这里放前面是要不加context先评估一次）
                        def get_refinement_result(turn, with_summary_or_code, with_precise_review_position):
                            max_attempts = 3
                            for i in range(max_attempts):
                                for j in range(max_attempts*2):
                                    if with_summary_or_code == "summary":
                                        ablation_result, _ablation_result = {"turn": turn, "ablation_info": "", "prompt_for_refinement_with_summary": "", "em": 0, "em_trim": 0, "bleu": 0, "bleu_trim": 0}, {"turn": turn, "ablation_info": "", "prompt_for_refinement_with_summary": "", "em": 0, "em_trim": 0, "bleu": 0, "bleu_trim": 0}
                                        prompt_for_refinement_with_summary = model.prompt_for_refinement(old_without_minus, record["review"], calls, reason_for_name_selection, turn, review_info, "summary", with_precise_review_position)
                                        new_code, answer = model.get_model_response(prompt_for_refinement_with_summary)
                                        ablation_result["prompt_for_refinement_with_summary"], _ablation_result["prompt_for_refinement_with_summary"] = prompt_for_refinement_with_summary.split('\n'), prompt_for_refinement_with_summary.split('\n')
                                    elif with_summary_or_code == "code":
                                        ablation_result, _ablation_result = {"turn": turn, "ablation_info": "", "prompt_for_refinement_with_code": "", "em": 0, "em_trim": 0, "bleu": 0, "bleu_trim": 0}, {"turn": turn, "ablation_info": "", "prompt_for_refinement_with_code": "", "em": 0, "em_trim": 0, "bleu": 0, "bleu_trim": 0}
                                        prompt_for_refinement_with_code = model.prompt_for_refinement(old_without_minus, record["review"], calls, reason_for_name_selection, turn, review_info, "code", with_precise_review_position)
                                        new_code, answer = model.get_model_response(prompt_for_refinement_with_code)
                                        ablation_result["prompt_for_refinement_with_code"], _ablation_result["prompt_for_refinement_with_code"] = prompt_for_refinement_with_code.split('\n'), prompt_for_refinement_with_code.split('\n')
                                    else: return None, None
                                    if not new_code: 
                                        print(f"Error attemption: 第{i+1}次尝试，第{j+1}次尝试，模型生成的new_code为空")
                                        print(f"answer: {answer}")
                                    if new_code: break
                                if not new_code: continue
                                new_code_lines = new_code.split('\n')
                                #用于去除new_code多生成的代码补全
                                end_line = record["old"].split('\n')[-1][1:]
                                index = -1
                                for i, line in enumerate(new_code_lines):
                                    if line.strip() == end_line.strip():
                                        index = i
                                if index != -1:
                                    new_code_lines_clipped = new_code_lines[:index+1]
                                    print(f"已在new_code中截取到{end_line}")
                                else: 
                                    new_code_lines_clipped = new_code_lines
                                    print(f"没有在new_code中找到{end_line}")
                                
                                em, em_trim, bleu, bleu_trim = model.calc_em_and_bleu(new, new_code)
                                if bleu + bleu_trim > ablation_result["bleu"] + ablation_result["bleu_trim"]: #取最好值
                                    ablation_result["em"], ablation_result["em_trim"], ablation_result["bleu"], ablation_result["bleu_trim"] = em, em_trim, bleu, bleu_trim
                                    ablation_result["new_code"] = new_code_lines
                                    ablation_result["new_code_groud_truth"] = new.split('\n')
                                em, em_trim, bleu, bleu_trim = model.calc_em_and_bleu(new, '\n'.join(new_code_lines_clipped))
                                if bleu + bleu_trim > _ablation_result["bleu"] + _ablation_result["bleu_trim"]: #取最好值
                                    _ablation_result["em"], _ablation_result["em_trim"], _ablation_result["bleu"], _ablation_result["bleu_trim"] = em, em_trim, bleu, bleu_trim
                                    _ablation_result["new_code_clipped"] = new_code_lines_clipped
                                    _ablation_result["new_code_groud_truth"] = new.split('\n')
                            return ablation_result, _ablation_result
                        
                        def execute_refinement_result(args):
                            try:
                                turn, type1, type2 = args
                                return get_refinement_result(turn, type1, type2)
                            except Exception as e:
                                print(f"Error processing ID {id}: {e}")
                                traceback.print_exc()
                                return None, None
                        
                        # partial_func = functools.partial(execute_refinement_result, turn)
                        if result["turn"] == 1:
                            # with mp.Pool(processes=4) as pool:
                            #     _results = pool.map(execute_refinement_result,
                            #                            [(turn, "summary", True),
                            #                             (turn, "summary", False)])
                            #     ablation_result1, ablation_result2 = _results[0]
                            #     ablation_result3, ablation_result4 = _results[1]
                            #     result["ablation_results"] = [ablation_result1, ablation_result2, ablation_result1, ablation_result2, ablation_result3, ablation_result4, ablation_result3, ablation_result4]
                            ablation_result1, ablation_result2 = get_refinement_result(turn, "summary", True)
                            ablation_result3, ablation_result4 = get_refinement_result(turn, "summary", False)
                            result["ablation_results"] = [ablation_result1, ablation_result2, ablation_result1, ablation_result2, ablation_result3, ablation_result4, ablation_result3, ablation_result4]
                        else:
                            # with mp.Pool(processes=4) as pool:
                            #     _results = pool.map(execute_refinement_result,
                            #                            [(turn, "summary", True),
                            #                             (turn, "code", True),
                            #                             (turn, "summary", False),
                            #                             (turn, "code", False)])
                            #     ablation_result1, ablation_result2 = _results[0]
                            #     ablation_result3, ablation_result4 = _results[1]
                            #     ablation_result5, ablation_result6 = _results[2]
                            #     ablation_result7, ablation_result8 = _results[3]
                            #     result["ablation_results"] = [ablation_result1, ablation_result2, ablation_result3, ablation_result4, ablation_result5, ablation_result6, ablation_result7, ablation_result8]
                            ablation_result1, ablation_result2 = get_refinement_result(turn, "summary", True)
                            ablation_result3, ablation_result4 = get_refinement_result(turn, "code", True)
                            ablation_result5, ablation_result6 = get_refinement_result(turn, "summary", False)
                            ablation_result7, ablation_result8 = get_refinement_result(turn, "code", False)
                            result["ablation_results"] = [ablation_result1, ablation_result2, ablation_result3, ablation_result4, ablation_result5, ablation_result6, ablation_result7, ablation_result8]
                        # 第四步：对比模型生成的结果和ground truth，给出ablation结果
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
                        for i in range(8):
                            result["ablation_results"][i]["ablation_info"] = ablation_info[i]

                        # 第三步：根据模型给出的结果，判断是否要继续寻找information，给出要查找的函数名
                        # 第一步：判断是否要继续寻找information，给出要查找的函数名
                        flag_for_context_change = False    #用于判断模型有没有给出有效的函数名以继续查找context
                        for i in range(max_attempts):
                            result["prompt_for_instruction"] = model.prompt_for_instruction(old_without_minus, record["review"], calls, turn, review_info, name_list)
                            _, result["result_json"] = model.get_model_response(result["prompt_for_instruction"])
                            if not result["result_json"]: 
                                result["flag_for_context_change"] = "case1:Unable to get the prompt_for_instruction result_json"
                                continue
                            if not reason_for_name_selection:
                                reason_for_name_selection = re.findall(r'"reason": "(.*?)",', result["result_json"])
                            name = re.findall(r'"function_name": "(.*?)",', result["result_json"])
                            if len(name) == 0:
                                result["flag_for_context_change"] = "case2:Unable to extract function name from the prompt_for_instruction result using regular expressions"
                                continue
                            name = name[0]
                            if name not in name_list: name_list.append(name)
                            #在definitions中查找name，并存入函数调用关系以及被调用函数的实现
                            
                            definition_name = next((definition for definition in definitions if definition['name'] == name), None)
                            if definition_name:
                                exist_name = next((call[1] for call in calls if call[1] == name), None)
                                if exist_name: #如果已经存在该函数的调用关系，则跳过
                                    result["flag_for_context_change"] = "case3:The function name has already existed"
                                    continue 
                                result['prompt_for_context'] = model.prompt_for_context(definition_name['text'])
                                _, context = model.get_model_response(result['prompt_for_context'])
                                result["prompt_for_context"] = result["prompt_for_context"].split('\n')
                                definition_name["context"] = context
                                calls.append((definition_name['caller'], name, definition_name['text'], definition_name['context']))
                                flag_for_context_change = True
                                break
                            else:
                                result["flag_for_context_change"] = "case4:Unable to find the definition of the function name"
                        #调整result的格式以方便阅读
                        result["prompt_for_instruction"] = result["prompt_for_instruction"].split('\n')
                        result["result_json"] = result["result_json"].split('\n')
                        # result["new_code_groud_truth"] = record["new"].split('\n')
                        results.append(result)
                    
                    record["results"] = results
                    record["context"] = json.dumps(definitions)
                    # record["llama_em"] = sum(result["em"] for result in results)/len(results)
                    # record["llama_em_trim"] = sum(result["em_trim"] for result in results)/len(results)
                    # record["llama_bleu"] = sum(result["bleu"] for result in results)/len(results)
                    # record["llama_bleu_trim"] = sum(result["bleu_trim"] for result in results)/len(results)

                    #写入文件
                    if not first_record:
                        f0.write(',\n')  # 写入逗号和换行
                    first_record = False
                    json.dump(record, f0, indent=4)
                    new_records.append(record)

                # except TimeoutError as e:
                #     print(f'Error processing ID {id}: Processing timed out after 600 seconds.')
                #     traceback.print_exc()
                except Exception as e:
                    print(f'Error processing ID {id}: {e}')
                    traceback.print_exc()
            print(f"All {len(new_records)} records processed")
        f0.write('\n]')
if __name__ == "__main__":
    main(-408)