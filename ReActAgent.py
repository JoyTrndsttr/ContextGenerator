from ContextGenerators.getContextGenerators import LanguageContextGenerator
import getProjectCommitState
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

class ReActAgent:
    def __init__(self, config_file, record):
        self.dataset_path = config_file['dataset_path']
        self.output_path = config_file['output_path']
        self.record = record
        self.id = record['_id']
        print(f'processing: {self.id}')
        self.old_without_minus = model.remove_prefix(record['old'])
        self.new_without_plus = model.remove_prefix(record['new'])
        self.new = record['new']
        self.turn, self.flag_for_context_change = 0, True
        # 获取仓库在commit提交前的状态
        self.get_commit_state()
        self.languageContextGenerator = LanguageContextGenerator(self.id)
        if not self.languageContextGenerator: return None
        self.contextGenerator = self.languageContextGenerator.context_generator
        self.review_info = self.languageContextGenerator.comment

    def get_commit_state(self, max_attempts=1):
        # 获取仓库在commit提交前的状态
        attempt = 0
        id = self.id
        while attempt < max_attempts:
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
    
    def get_refinement_result(self, with_summary_or_code, with_precise_review_position, clipped_flag):
        old_without_minus, record, calls, turn, review_info = self.old_without_minus, self.record, self.calls, self.turn, self.review_info
        max_attempts = 3
        for i in range(max_attempts):
            # for j in range(max_attempts*2):
            ablation_result = {"turn": turn, "ablation_info": "", "prompt_for_refinement": "", "em": 0, "em_trim": 0, "bleu": 0, "bleu_trim": 0}
            prompt_for_refinement = model.prompt_for_refinement(old_without_minus, record["review"], calls, review_info, with_summary_or_code, with_precise_review_position, clipped_flag)
            new_code, answer = model.get_model_response(prompt_for_refinement)
            ablation_result["prompt_for_refinement"] = prompt_for_refinement.split('\n')
                # if not new_code: 
                #     print(f"Error attemption: 第{i+1}次尝试，第{j+1}次尝试，模型生成的new_code为空")
                #     print(f"answer: {answer}")
                # if new_code: break
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
                ablation_result["new_code"] = new_code.split('\n')
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
            ablation_result1 = self.get_refinement_result("summary", True, True)
            ablation_result2 = self.get_refinement_result("summary", True, False)
            ablation_result3 = self.get_refinement_result("code", True, True)
            ablation_result4 = self.get_refinement_result("code", True, False)
            ablation_result5 = self.get_refinement_result("summary", False, True)
            ablation_result6 = self.get_refinement_result("summary", False, False)
            ablation_result7 = self.get_refinement_result("code", False, True)
            ablation_result8 = self.get_refinement_result("code", False, False)
            result["ablation_results"] = [ablation_result1, ablation_result2, ablation_result3, ablation_result4, ablation_result5, ablation_result6, ablation_result7, ablation_result8]
            # result["ablation_results"] = [ablation_result1]
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
            for i in range(len(result["ablation_results"])):
                result["ablation_results"][i]["ablation_info"] = ablation_info[i]

            # 第一步：判断是否要继续寻找information，给出要查找的函数名
            flag_for_context_change = False    #用于判断模型有没有给出有效的函数名以继续查找context
            max_attempts = 3
            for i in range(max_attempts):
                result["prompt_for_instruction"] = model.prompt_for_instruction(old_without_minus, record["review"], self.calls, review_info, name_list)
                _, result["result_json"] = model.get_model_response(result["prompt_for_instruction"])
                if not result["result_json"]: 
                    result["flag_for_context_change"] = "case1:Unable to get the prompt_for_instruction result_json"
                    continue
                # if not reason_for_name_selection:
                #     reason_for_name_selection = re.findall(r'"reason": "(.*?)",', result["result_json"])
                name = re.findall(r'"function_name": "(.*?)",', result["result_json"])
                if len(name) == 0:
                    result["flag_for_context_change"] = "case2:Unable to extract function name from the prompt_for_instruction result using regular expressions"
                    continue
                name = name[0]
                if name not in name_list: name_list.append(name)
                #在definitions中查找name，并存入函数调用关系以及被调用函数的实现
                
                definition_name = next((definition for definition in definitions if definition['name'] == name), None)
                if definition_name:
                    if definition_name == "default_function":
                        result["flag_for_context_change"] = "case5:No need to check more information"
                        continue
                    exist_name = next((call[1] for call in self.calls if call[1] == name), None)
                    if exist_name: #如果已经存在该函数的调用关系，则跳过
                        result["flag_for_context_change"] = "case3:The function name has already existed"
                        continue 
                    result['prompt_for_context'] = model.prompt_for_summary(definition_name['text'])
                    _, context = model.get_model_response(result['prompt_for_context'])
                    result["prompt_for_context"] = result["prompt_for_context"].split('\n')
                    definition_name["context"] = context
                    self.calls.append((definition_name['caller'], name, definition_name['text'], definition_name['context']))
                    flag_for_context_change = True
                    break
                else:
                    result["flag_for_context_change"] = "case4:Unable to find the definition of the function name"
            #调整result的格式以方便阅读
            result["prompt_for_instruction"] = result["prompt_for_instruction"].split('\n')
            result["result_json"] = result["result_json"].split('\n')
            # result["new_code_groud_truth"] = record["new"].split('\n')
            results.append(result)
        return definitions, results

def process_repo_group(config, repo, records):
    """处理同repo的所有records（Linux优化版）"""
    try:
        # 计算文件分片索引（0-9）
        file_idx = int(hashlib.md5(repo.encode()).hexdigest(), 16) % 10
        output_dir = config['output_path'].rstrip('/')
        output_file = f"{output_dir}/result_{file_idx}.json"
        
        # 处理所有records
        results = []
        for record in records:
            id = record['_id']
            try:
                agent = ReActAgent(config, record)
                record["definitions"], record["results"] = agent.process()
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
    config = {
        "dataset_path": '/mnt/ssd2/wangke/CR_data/dataset/cacr_python_all.json',
        "output_path": '/mnt/ssd2/wangke/CR_data/dataset/map_result/'
    }

    # 读取数据集
    with open(config["dataset_path"], "r", encoding="utf-8") as f:
        records = json.load(f)
        # records = [record for record in records if record["id"] < 0]
    
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