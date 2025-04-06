from ContextGenerators.LanguageContextGeneratorManager import LanguageContextGenerator
import getProjectCommitState
from getProjectCommitState import CLBPP
import logging
import ErrorProcess
import json
import model
import re
import traceback
import os
import multiprocessing
# import pathos.multiprocessing as mp
import multiprocessing as mp
from collections import defaultdict
import hashlib

class AgentRefiner:
    def __init__(self, config_file, record):
        self.dataset_path = config_file['dataset_path']
        self.output_path = config_file['output_path']
        self.record = CLBPP(record)
        self.id = record['_id']
        print(f'processing: {self.id}')
        self.old_without_minus = model.remove_prefix(record['old'])
        self.new_without_plus = model.remove_prefix(record['new'])
        self.new = record['new']
        self.turn, self.flag_for_context_change = 0, True
        self.languageContextGenerator = LanguageContextGenerator(self.record)
        if not self.languageContextGenerator: return None
        self.contextGenerator = self.languageContextGenerator.context_generator
        self.review_info = self.languageContextGenerator.comment

    def get_refinement_result(self, with_summary_or_code, with_precise_review_position, clipped_flag):
        old_without_minus, record, calls, turn, review_info, in_file_context_summary, cross_file_context_summary = self.old_without_minus, self.record, self.calls, self.turn, self.review_info, self.in_file_context_summary, self.cross_file_context_summary
        max_attempts = 1
        for i in range(max_attempts):
            ablation_result = {"turn": turn, "ablation_info": "", "prompt_for_refinement": "", "em": 0, "em_trim": 0, "bleu": 0, "bleu_trim": 0}
            # in_file_context_summary = "" 
            prompt_for_refinement = model.prompt_for_refinement(old_without_minus, record["review"], calls, review_info, with_summary_or_code, with_precise_review_position, clipped_flag, in_file_context_summary, cross_file_context_summary)
            new_code, answer = model.get_model_response(prompt_for_refinement)
            # new_code, think, answer = model.get_full_deepseek_response(prompt_for_refinement)
            # ablation_result["think"] = think.split('\n')
            ablation_result["prompt_for_refinement"] = prompt_for_refinement.split('\n')
            if not new_code: continue
            new_code_lines = new_code.split('\n')

            if clipped_flag:
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
                new_code_lines = new_code_lines_clipped
                new_code = '\n'.join(new_code_lines_clipped)

            # 获取稳定的结果
            em, em_trim, bleu, bleu_trim = model.calc_em_and_bleu(self.new, new_code)
            if bleu + bleu_trim > ablation_result["bleu"] + ablation_result["bleu_trim"]: #取最好值
                ablation_result["em"], ablation_result["em_trim"], ablation_result["bleu"], ablation_result["bleu_trim"] = em, em_trim, bleu, bleu_trim
                ablation_result["new_code"] = new_code_lines
                ablation_result["new_code_groud_truth"] = self.new.split('\n')

        return ablation_result

    def get_json_value_number(self, str, key):
        try:
            return re.search(r'(\d+)', str.split(key)[1]).group(0)
        except:
            return "0"
    
    def get_json_value_string(self, str, key):
        try:
            return re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', str).group(1)
        except:
            return ""

    def process(self):
        # ReAct框架
        turn, flag_for_context_change, contextGenerator, old_without_minus, record, review_info = self.turn, self.flag_for_context_change, self.contextGenerator, self.old_without_minus, self.record, self.review_info
        self.calls = [] #元组格式，（调用的函数，被调用的函数，被调用函数的实现）
        results = [] #存储每一个turn的结果
        name = "" #存储要检索的函数名
        name_list = [] #存储所有函数名
        definitions = [] #存储所有上下文定义
        self.in_file_context_summary = ""
        self.cross_file_context_summary = ""

        #先运行一次refinement作为turn0的结果
        results.append({"turn": 0, "result_json": "", "prompt_for_instruction": [], "flag_for_context_change": "",  "ablation_results": [self.get_refinement_result("summary", True, False)]})

        #1. Instruction 阶段
        #判断是否需要额外的上下文信息，包括In-file context和Cross-file context
        prompt_for_additional_context_required = model.prompt_for_additional_context_required(old_without_minus, record["review"])
        _, think_for_additional_context_required, additional_context_required_result_json = model.get_full_deepseek_response(prompt_for_additional_context_required)
        in_file_context_required = self.get_json_value_number(additional_context_required_result_json, "In_file_context_required")
        question_for_in_file_context = self.get_json_value_string(additional_context_required_result_json, "Your_question_for_in_file_context")
        cross_file_context_required = self.get_json_value_number(additional_context_required_result_json, "Cross_file_context_required")
        question_for_cross_file_context = self.get_json_value_string(additional_context_required_result_json, "Your_question_for_cross_file_context")
        record["additional_context_required"] = {
            "in_file_context_required": in_file_context_required,
            "question_for_in_file_context": question_for_in_file_context,
            "cross_file_context_required": cross_file_context_required,
            "question_for_cross_file_context": question_for_cross_file_context,
            "additional_context_required_result_json": additional_context_required_result_json.split('\n'),
            "think_for_additional_context_required": think_for_additional_context_required.split('\n')
        }
        if in_file_context_required == "0" and cross_file_context_required == "0":
            results[0]["flag_for_context_change"] = "case:No additional context required"

        #1.1 处理In-file context
        if in_file_context_required == "1":
            in_file_context = contextGenerator._source_code
            #3.1 Summary In-file context
            in_file_context_summary_useful = "0"
            for i in range(3): #Validation feedback loop
                prompt_for_in_file_context_summary = model.prompt_for_in_file_context_summary(record["review"], in_file_context, question_for_in_file_context)
                _, think_for_in_file_context_summary, in_file_context_summary = model.get_full_deepseek_response(prompt_for_in_file_context_summary)
                in_file_context_summary = self.get_json_value_string(in_file_context_summary, "Summary")
                record["in_file_context_summary"] = {
                    "in_file_context_summary": in_file_context_summary,
                    "think_for_in_file_context_summary": think_for_in_file_context_summary.split('\n')
                }
                prompt_for_evaluating_summary = model.prompt_for_evaluating_summary(old_without_minus, record["review"], question_for_in_file_context, in_file_context_summary)
                _, think_for_evaluating_summary, evaluating_summary_result = model.get_full_deepseek_response(prompt_for_evaluating_summary)
                question_resolved = self.get_json_value_number(evaluating_summary_result, "Question_resolved")
                new_question = self.get_json_value_string(evaluating_summary_result, "New_question")
                in_file_context_summary_useful = self.get_json_value_number(evaluating_summary_result, "Summary_useful")
                record["evaluating_summary"] = {
                    "question_resolved": question_resolved,
                    "new_question": new_question,
                    "evaluating_summary_result": evaluating_summary_result.split('\n'),
                    "think_for_evaluating_summary": think_for_evaluating_summary.split('\n')
                }
                if in_file_context_summary_useful == "1":
                    self.in_file_context_summary = in_file_context_summary
                    break
                else:
                    if new_question: question_for_in_file_context = new_question

        #再运行一次refinement作为turn1的结果,此结果中已包含In-file context
        results.append({"turn": 1, "result_json": "", "prompt_for_instruction": [], "flag_for_context_change": "",  "ablation_results": [self.get_refinement_result("summary", True, False)]})
        turn = 1

        #1.2 处理Cross-file context
        if cross_file_context_required == "1":
            while turn < 6 and flag_for_context_change:
                turn += 1
                self.turn = turn
                print(f"turn: {turn}")
                result = {"turn": turn, "result_json": "", "prompt_for_instruction": "","flag_for_context_change": "",  "ablation_results": []}
                flag_for_context_change = False    #用于判断模型有没有给出有效的函数名以继续查找context
                if name: contextGenerator.updateSource(name)
                definitions = contextGenerator.getContext()

                prompt_for_cross_file_context_request = model.prompt_for_cross_file_context_request(old_without_minus, record["review"], question_for_cross_file_context, self.calls, name_list)
                _, think_for_cross_file_context_request, cross_file_context_request_result_json = model.get_full_deepseek_response(prompt_for_cross_file_context_request)
                additional_context_required = self.get_json_value_number(cross_file_context_request_result_json, "Additional_context_required")
                try: element_name_to_retrieve = re.search(r'[a-zA-Z_]+', cross_file_context_request_result_json.split("Element_name_to_retrieve")[1]).group(0) 
                except: 
                    result["flag_for_context_change"] = "case:Failed to extract element name from the prompt_for_instruction result using regular expressions"
                    record["unfinished_result"] = result
                    continue
                question_for_element = self.get_json_value_string(cross_file_context_request_result_json, "Question_for_element")
                result["cross_file_context_request"] = {
                    "additional_context_required": additional_context_required,
                    "element_name_to_retrieve": element_name_to_retrieve,
                    "question_for_element": question_for_element,
                    "cross_file_context_request_result_json": cross_file_context_request_result_json.split('\n'),
                    "think_for_cross_file_context_request": think_for_cross_file_context_request.split('\n')
                }
                name = element_name_to_retrieve
                if name not in name_list: name_list.append(name)

                #2. Action 阶段
                #在definitions中查找name，并存入函数调用关系以及被调用函数的实现
                definition_name = next((definition for definition in definitions if definition['name'] == name), None)
                if not definition_name:
                    #扩大搜索范围
                    definitions = contextGenerator.search_definition(name)
                    definition_name = next((definition for definition in definitions if definition['name'] == name), None)
                if not definition_name:
                    result["flag_for_context_change"] = "case:Unable to find the definition of the function name"
                    record["unfinished_result"] = result
                    continue
                if next((call[1] for call in self.calls if call[1] == name), None): #如果已经存在该函数的调用关系，则跳过
                    result["flag_for_context_change"] = "case:The function name has already existed"
                    record["unfinished_result"] = result
                    continue 
                self.calls.append((definition_name['caller'], name, definition_name['text'], "<definition_name['context']>" , question_for_element))
                
                #3. Summary阶段
                #3.2 Summary Cross-file context
                for i in range(3): #Validation feedback loop
                    prompt_for_cross_file_context_summary = model.prompt_for_cross_file_context_summary(record["review"], question_for_cross_file_context, self.calls)
                    _, think_for_cross_file_context_summary, cross_file_context_summary = model.get_full_deepseek_response(prompt_for_cross_file_context_summary)
                    cross_file_context_summary = self.get_json_value_string(cross_file_context_summary, "Summary")
                    definition_name["context"] = cross_file_context_summary
                    self.calls.pop()
                    self.calls.append((definition_name['caller'], name, definition_name['text'], definition_name['context'] , question_for_element))
                    result["cross_file_context_summary"] = {
                        "cross_file_context_summary_useful": "0",
                        "cross_file_context_summary": cross_file_context_summary,
                        "think_for_cross_file_context_summary": think_for_cross_file_context_summary.split('\n')
                    }
                    prompt_for_evaluating_summary = model.prompt_for_evaluating_summary(old_without_minus, record["review"], question_for_cross_file_context, cross_file_context_summary)
                    _, think_for_evaluating_summary, evaluating_summary_result = model.get_full_deepseek_response(prompt_for_evaluating_summary)
                    question_resolved = self.get_json_value_number(evaluating_summary_result, "Question_resolved")
                    cross_file_context_summary_useful = self.get_json_value_number(evaluating_summary_result, "Summary_useful")
                    new_question = self.get_json_value_string(evaluating_summary_result, "New_question")
                    result["evaluating_summary"] = {
                        "question_resolved": question_resolved,
                        "new_question": new_question,
                        "evaluating_summary_result": evaluating_summary_result.split('\n'),
                        "think_for_evaluating_summary": think_for_evaluating_summary.split('\n')
                    }
                    if cross_file_context_summary_useful == "1":
                        self.cross_file_context_summary = cross_file_context_summary
                        break
                    else:
                        if new_question: question_for_cross_file_context = new_question
                
                #4：Refinement Stage
                ablation_result2 = self.get_refinement_result("summary", True, False)
                # result["ablation_results"] = [ablation_result1, ablation_result2, ablation_result3, ablation_result4, ablation_result5, ablation_result6, ablation_result7, ablation_result8]
                result["ablation_results"] = [ablation_result2]
                # ablation_info = [
                #     "Summary_cut_precise",
                #     "Summary_uncut_precise",
                #     "Code_cut_precise",
                #     "Code_uncut_precise",
                #     "Summary_cut_default",
                #     "Summary_uncut_default",
                #     "Code_cut_default",
                #     "Code_uncut_default"
                # ]
                # for i in range(len(result["ablation_results"])):
                #     result["ablation_results"][i]["ablation_info"] = ablation_info[i]
                results.append(result)
                flag_for_context_change = True #没有被任何的continue语句跳过
        record["definitions"], record["results"] = "omitted", results
        return record

def process_repo_group(config, repo, records):
    """处理同repo的所有records（Linux优化版）"""
    try:
        output_file = config['output_path']

        # 处理所有records
        results = []
        for record in records:
            id = record['_id']
            try:
                agent = AgentRefiner(config, record)
                record = agent.process()
                # 原子化写入操作（追加模式）
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
            except Exception as e:
                print(f'Error processing ID {id}: {e}')
                traceback.print_exc()
                continue
        return (repo, "success", len(results))
    except Exception as e:
        traceback.print_exc()
        return (repo, f"failed: {str(e)}", 0)

def main():
    # config = {
    #     "dataset_path": '/mnt/ssd2/wangke/dataset/cr_data/dataset_sorted_llama_instructed_map_deepseek_processed.json',
    #     "output_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/map_result.json',
    #     "record_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/result.json',
    # }
    # config = {
    #     "dataset_path": '/mnt/ssd2/wangke/dataset/cr_data/new_datasets_instructed_map_deepseek_processed.json',
    #     "output_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/new_map_result.json',
    #     "record_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/new_result.json',
    # }
    # config = {
    #     "dataset_path": '/mnt/ssd2/wangke/dataset/cr_data/new_datasets_instructed_map_deepseek_processed.json',
    #     "output_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/new_map_result_deepseek.json',
    #     "record_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/new_result_deepseek.json',
    # }
    # config = {
    #     "dataset_path": '/mnt/ssd2/wangke/dataset/cr_data/dataset_sorted_llama_instructed_map_deepseek_processed.json',
    #     "output_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/tmp_result.json',
    #     "record_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/_tmp_result.json',
    # }
    # config = {
    #     "dataset_path": '/mnt/ssd2/wangke/dataset/cr_data/dataset_sorted_llama_instructed_map_deepseek_processed.json',
    #     "output_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/result_4_3.json',
    #     # "record_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/_tmp_result.json',
    # }
    config = {
        "dataset_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/CR_and_CRN_estimated.json',
        "output_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/result_4_6.json',
        # "record_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/_tmp_result.json',
    }
    

    #继续处理未完成的记录
    # with open(config["record_path"], "r", encoding="utf-8") as f0:
    #     _records = json.load(f0)
    #     ids = [record["_id"] for record in _records]

    # 读取数据集
    with open(config["dataset_path"], "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
        # records = json.load(f)
        # records = [record for record in records if record["_id"] not in ids]
        print(f"待处理记录数: {len(records)}")

    # # 测试单个记录
    # # config["output_path"] = '/mnt/ssd2/wangke/dataset/AgentRefiner/tmp_result.json'
    # record = [record for record in records if record["_id"] == -5988]
    # # record = [records[0]]
    # process_repo_group(config, record[0]["repo"], record)
    # return

    # 按repo分组（确保同repo顺序处理）
    repo_map = defaultdict(list)
    for record in records:
        repo_map[record["repo"]].append(record)

    # Linux专用设置
    mp.set_start_method('fork')  # 明确设置进程启动方式

    # 创建进程池处理分组数据
    with mp.Pool(10) as pool:
        tasks = [(config, repo, records) for repo, records in repo_map.items()]

        # 获取详细处理结果
        processed_results = pool.starmap(process_repo_group, tasks)

        # 统计输出
        total_success = sum(r[2] for r in processed_results if r[1] == "success")
        failed_repos = [r[0] for r in processed_results if r[1] != "success"]

        print(f"成功处理记录数: {total_success}/{len(records)}")
        print(f"失败仓库数: {len(failed_repos)}")
        if failed_repos:
            print("失败仓库列表:", ", ".join(failed_repos))

if __name__ == "__main__":
    main()
    # pass