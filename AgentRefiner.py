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
        old_without_minus, record, calls, turn, review_info = self.old_without_minus, self.record, self.calls, self.turn, self.review_info
        max_attempts = 3
        for i in range(max_attempts):
            ablation_result = {"turn": turn, "ablation_info": "", "prompt_for_refinement": "", "em": 0, "em_trim": 0, "bleu": 0, "bleu_trim": 0}
            prompt_for_refinement = model.prompt_for_refinement(old_without_minus, record["review"], calls, review_info, with_summary_or_code, with_precise_review_position, clipped_flag)
            new_code, answer = model.get_model_response(prompt_for_refinement)
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

    def process(self):
        # ReAct框架
        turn, flag_for_context_change, contextGenerator, old_without_minus, record, review_info = self.turn, self.flag_for_context_change, self.contextGenerator, self.old_without_minus, self.record, self.review_info
        self.calls = [] #元组格式，（调用的函数，被调用的函数，被调用函数的实现）
        results = [] #存储每一个turn的结果
        name = "" #存储要检索的函数名
        name_list = [] #存储所有函数名
        while turn < 6 and flag_for_context_change:
            turn += 1
            self.turn = turn
            print(f"turn: {turn}")
            if name: contextGenerator.updateSource(name)
            definitions = contextGenerator.getContext()
            result = {"turn": turn, "result_json": "", "prompt_for_instruction": "","flag_for_context_change": "",  "ablation_results": []}
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

            # 第一步：判断是否要继续寻找information，给出要查找的函数名
            flag_for_context_change = False    #用于判断模型有没有给出有效的函数名以继续查找context
            max_attempts = 1
            for i in range(max_attempts):
                result["prompt_for_instruction"] = model.prompt_for_instruction(old_without_minus, record["review"], self.calls, review_info, name_list)
                _, result["result_json"] = model.get_deepseek_response(result["prompt_for_instruction"])
                if not result["result_json"]: 
                    result["flag_for_context_change"] = "case1:Unable to get the prompt_for_instruction result_json"
                    continue
                try:
                    result_json = result["result_json"]
                    additional_context_required = re.search(r'(\d+)', result_json.split("Additional_context_required")[1]).group(0)
                    if additional_context_required == "0":
                        result["flag_for_context_change"] = "case5:LLM does not require additional context"
                        continue
                    element_name_to_retrieve = re.search(r'[a-zA-Z_]+', result_json.split("Element_name_to_retrieve")[1]).group(0)
                    details_to_retrieve = re.search(r'"Details_to_retrieve"\s*:\s*"((?:[^"\\]|\\.)*)"', result_json).group(1)
                    name = element_name_to_retrieve
                    if name not in name_list: name_list.append(name)
                except Exception as e:
                    result["flag_for_context_change"] = "case2:Failed to extract information from the prompt_for_instruction result using regular expressions"
                    continue

                #在definitions中查找name，并存入函数调用关系以及被调用函数的实现
                definition_name = next((definition for definition in definitions if definition['name'] == name), None)
                if not definition_name:
                    #扩大搜索范围
                    definitions = contextGenerator.search_definition(name)
                    definition_name = next((definition for definition in definitions if definition['name'] == name), None)
                    
                if definition_name:
                    exist_name = next((call[1] for call in self.calls if call[1] == name), None)
                    if exist_name: #如果已经存在该函数的调用关系，则跳过
                        result["flag_for_context_change"] = "case3:The function name has already existed"
                        continue 
                    result['prompt_for_summary'] = model.prompt_for_summary(definition_name['text'], self.calls)
                    _, context = model.get_deepseek_response(result['prompt_for_summary'])
                    result["prompt_for_summary"] = result["prompt_for_summary"].split('\n')
                    definition_name["context"] = context
                    self.calls.append((definition_name['caller'], name, definition_name['text'], definition_name['context']), details_to_retrieve)
                    flag_for_context_change = True
                    break
                else:
                    result["flag_for_context_change"] = "case4:Unable to find the definition of the function name"
            #调整result的格式以方便阅读
            result["prompt_for_instruction"] = result["prompt_for_instruction"].split('\n')
            result["result_json"] = result["result_json"].split('\n')
            # result["new_code_groud_truth"] = record["new"].split('\n')
            results.append(result)
        record["definitions"], record["results"] = definitions, results
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
    #     "dataset_path": '/mnt/ssd2/wangke/CR_data/dataset/cacr_python_all.json',
    #     "output_path": '/mnt/ssd2/wangke/CR_data/dataset/map_result/',
    #     "record_path": '/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_llama.json'
    # }
    config = {
        "dataset_path": '/mnt/ssd2/wangke/dataset/cr_data/dataset_sorted_llama_instructed_map_deepseek_processed.json',
        "output_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/map_result.json',
        "record_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/result.json',
    }

    #继续处理未完成的记录
    # with open(config["record_path"], "r", encoding="utf-8") as f0:
    #     _records = json.load(f0)
    #     ids = [record["_id"] for record in _records]

    # 读取数据集
    with open(config["dataset_path"], "r", encoding="utf-8") as f:
        # records = [json.loads(line) for line in f]
        records = json.load(f)
        # records = [record for record in records if record["_id"] not in ids]
        print(f"待处理记录数: {len(records)}")

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