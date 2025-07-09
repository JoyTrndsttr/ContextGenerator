from ContextGenerators.LanguageContextGeneratorManager import LanguageContextGenerator
from getProjectCommitState import CLBPP
import json
import model
import re
import traceback
import multiprocessing as mp
from collections import defaultdict
import time
from utils.Guo_2025_utils import get_samples
import random

class AgentRefiner:
    def __init__(self, config_file, record):
        self.dataset_path = config_file['dataset_path']
        self.output_path = config_file['output_path']
        self.log_path = config_file['log_path']
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
        self.question_for_in_file_context, self.in_file_context_summary, self.question_for_cross_file_context, self.cross_file_context_summary = "", "", "", ""

    def get_refinement_result(self, prompt_type = "vallina", llm = "llama", intention = False, with_review_line = True):
        def get_code_from_response(response):
            # 1. 提取model_code，被```包裹的部分
            try:
                pattern = re.compile(r"```(.*?)```", re.S)
                model_code = pattern.findall(response)[-1]
            except:
                print("error id:", id)
                model_code = response
            # 2. 按行分割，第一行注意是python或其他语言描述，要舍弃
            model_code_lines = model_code.split("\n")
            model_code_lines = model_code_lines[1:]
            model_code = "\n".join(model_code_lines)
            return model_code
        
        old_without_minus, record, turn, review_info = self.old_without_minus, self.record, self.turn, self.review_info
        ablation_result = {"turn": turn, "ablation_info": "", "prompt_for_refinement": "", "em": 0, "em_trim": 0, "bleu": 0, "bleu_trim": 0}
        # 获取vallina, self_generated, rag提示词
        if prompt_type == "vallina":
            # prompt_for_refinement = model.prompt_for_refinement(old_without_minus, record["review"], review_info if with_review_line else None, self.question_for_in_file_context, self.in_file_context_summary, self.question_for_cross_file_context, self.cross_file_context_summary)
            prompt_for_refinement = model.simple_prompt(record["review"], old_without_minus, review_info["review_position_line"])
        elif prompt_type == "self_generated":
            data = {
                "comment": record["review"],
                "review_line": review_info["review_position_line"],
                "old_code": old_without_minus
            }
            system_prompt_for_intention, prompt_for_intention = model.get_intention_prompt(data)
            _, data["intention"] = model.request(llm, prompt_for_intention, system_prompt_for_intention)
            prompt_for_refinement = model.get_selfgen_prompt(data)
        elif prompt_type == "rag":
            prompt_for_refinement = model.simple_prompt_with_rag(record["review"], old_without_minus, review_info["review_position_line"], get_samples(record["review"]))
        elif prompt_type == "in-file-context":
            prompt_for_refinement = model.simple_prompt_with_in_file_context(record["review"], old_without_minus, review_info["review_position_line"], self.in_file_context_summary)
        elif prompt_type == "cross-file-context":
            prompt_for_refinement = model.simple_prompt_with_cross_file_context(record["review"], old_without_minus, review_info["review_position_line"], self.in_file_context_summary, self.cross_file_context_summary)
        else: raise ValueError("Invalid prompt_type")
        # 获取refine后的代码
        new_code, answer = model.request(llm, prompt_for_refinement)
        ablation_result["prompt_for_refinement"] = prompt_for_refinement.split('\n')
        if not new_code: ablation_result
        # if intention:
        if True:
            # 这里统一采用Guo2025的截取方法
            last_code_block = get_code_from_response(answer)
            if last_code_block:
                new_code = last_code_block
        new_code_lines = new_code.split('\n') if new_code else []
        # 评估
        em, em_trim, bleu, bleu_trim = model.calc_em_and_bleu(self.new, new_code)
        ablation_result["em"], ablation_result["em_trim"], ablation_result["bleu"], ablation_result["bleu_trim"] = em, em_trim, bleu, bleu_trim
        ablation_result["new_code"] = new_code_lines
        ablation_result["new_code_groud_truth"] = self.new.split('\n')

        # 获取code block所在文件的源代码
        file_path = self.contextGenerator.file_path
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.readlines()
        except Exception as e:
            print(f"Error processing patch for {file_path}: {e}")
        pre_file_content = file_content.copy() # 备份文件内容，每次refine以及评估完恢复
        
        try:
            # 手动构造模型生成的new code的补丁并应用到源文件中，以获取Identifier_Match
            diff = self.record["diff_hunk"]
            diff_lines = diff.split('\n')
            prefix_line = diff_lines[0]
            old_diff_lines = [line for line in diff_lines[1:] if not line.startswith('+')]
            old_diff_lines = [f"-{line[1:]}" for line in old_diff_lines]
            new_code_lines = ablation_result["new_code"]
            new_code_lines = [f"+{line}" for line in new_code_lines]
            diff = '\n'.join([prefix_line] + old_diff_lines + new_code_lines)
            
            # 应用生成的补丁
            start_line = None
            line_change = 0 #补丁所在行修正
            for line in diff.split('\n'):# 解析补丁并应用到文件
                if line.startswith('@@'):
                    start_line = int(line.split()[1].split(',')[0][1:]) - 2 + line_change
                    if start_line == -2 : start_line = -1 #修正@@号初始值为0带来的影响
                elif line.startswith('+') and start_line is not None:
                    file_content.insert(start_line, line[1:] + '\n')
                    line_change += 1
                elif line.startswith('-') and start_line is not None:
                    if start_line < len(file_content):
                        del file_content[start_line]
                        line_change -= 1
                        start_line -= 1
                    else:
                        print(f"Warning: Trying to delete line {start_line} which is out of range in {file_path}")
                start_line += 1
            with open(file_path, 'w', encoding='utf-8') as file:
                file.writelines(file_content)

            # 提取new_added_identifiers, 计算Identifier_Match
            _languageContextGenerator = LanguageContextGenerator(record)
            _languageContextGenerator.code_diff = diff
            contextGenerator = _languageContextGenerator.get_context_generator("revised")
            definitions_after_patch = contextGenerator.node_list
            predict_new_identifiers = [def_aft.text.decode('utf-8') for def_aft in definitions_after_patch]
            predict_new_identifiers = list(set(predict_new_identifiers))
            ablation_result["predict_new_identifiers"] = predict_new_identifiers
            ablation_result["ground_truth_identifiers"] = self.record["new_identifiers"]
            ablation_result["generated_patch"] = diff.split('\n')
            ground_truth_identifiers = self.record["new_identifiers"]
            recall = len(set(predict_new_identifiers) & set(ground_truth_identifiers)) / len(ground_truth_identifiers) if len(ground_truth_identifiers) > 0 else 0
            precision = len(set(predict_new_identifiers) & set(ground_truth_identifiers)) / len(predict_new_identifiers) if len(predict_new_identifiers) > 0 else 0
            f1_score = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0
            ablation_result["Identifie_Match"] = {
                "recall": recall,
                "precision": precision,
                "f1_score": f1_score
            }
            old_identifies = self.record["old_identifiers"]
            predict_new_added_identifiers = list(set(predict_new_identifiers) - set(old_identifies))
            ablation_result["predict_new_added_identifiers"] = predict_new_added_identifiers
            ablation_result["ground_truth_added_identifiers"] = self.record["new_added_identifiers"]
            ground_truth_added_identifiers = self.record["new_added_identifiers"]
            recall = len(set(predict_new_added_identifiers) & set(ground_truth_added_identifiers)) / len(ground_truth_added_identifiers) if len(ground_truth_added_identifiers) > 0 else 0
            precision = len(set(predict_new_added_identifiers) & set(ground_truth_added_identifiers)) / len(predict_new_added_identifiers) if len(predict_new_added_identifiers) > 0 else 0
            f1_score = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0
            ablation_result["Added_Identifie_Match"] = {
                "recall": recall,
                "precision": precision,
                "f1_score": f1_score
            }
            with open(file_path, 'w', encoding='utf-8') as file:
                file.writelines(pre_file_content)
        except Exception as e:
            print(f"Error processing generated code for {self.id}: {e}")
            traceback.print_exc()
            ablation_result["Identifie_Match"] = {
                "recall": 0,
                "precision": 0,
                "f1_score": 0
            }
            with open(file_path, 'w', encoding='utf-8') as file:
                file.writelines(pre_file_content)
        
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
        
    def get_json_value_string_list(self, str, key):
        try:
            pattern = rf'"{key}"\s*:\s*\[([^\]]*)\]'
            match = re.search(pattern, str)
            if not match:
                return []
            content = match.group(1)
            return re.findall(r'"([^"]+)"', content)
        except:
            return []

    def log_processed_record(self, id):
        with open(self.log_path, 'a', encoding='utf-8') as file:
            file.write(f"{id}\n")
    
    def process(self):
        # ReAct框架
        turn, flag_for_context_change, contextGenerator, old_without_minus, record, review_info = self.turn, self.flag_for_context_change, self.contextGenerator, self.old_without_minus, self.record, self.review_info
        self.calls = [] #元组格式，（调用的函数，被调用的函数，被调用函数的实现）
        results = [] #存储每一个turn的结果
        record["call_name_list"] = []
        record["Evaluation_Results"] = {
            "Recall@Context": 0,
            "Precision@Context": 0,
            "F1@Context": 0,
        }

        #第一次运行：获取Vallina的结果
        self.turn, turn = 1, 1
        results.append({"turn": 1, "result_json": "", "prompt_for_instruction": [], "flag_for_context_change": "",  "ablation_results": [
            self.get_refinement_result(), 
            # self.get_refinement_result(llm="deepseek"),
            self.get_refinement_result(llm="deepseek_r1")
            ]})
        
        #第二次运行：获取self-generated的结果
        self.turn, turn = 2, 2
        results.append({"turn": 2, "result_json": "", "prompt_for_instruction": [], "flag_for_context_change": "",  "ablation_results": [
            self.get_refinement_result(prompt_type="self_generated", intention=True),
            # self.get_refinement_result(prompt_type="self_generated", llm="deepseek", intention=True),
            self.get_refinement_result(prompt_type="self_generated", llm="deepseek_r1", intention=True)
            ]})
        
        #第三次运行：获取RAG的结果
        self.turn, turn = 3, 3
        results.append({"turn": 3, "result_json": "", "prompt_for_instruction": [], "flag_for_context_change": "",  "ablation_results": [
            self.get_refinement_result(prompt_type="rag"),
            # self.get_refinement_result(prompt_type="rag", llm="deepseek"),
            self.get_refinement_result(prompt_type="rag", llm="deepseek_r1")
            ]})

        #第四次运行：获取In-file context的结果
        #1.1 处理In-file context
        # if in_file_context_required == "1":
        if True:
            in_file_context = contextGenerator._source_code
            self.in_file_context = in_file_context
            #3.1 Summary In-file context
            prompt_for_in_file_context_summary = model.prompt_for_in_file_context_summary_without_question(record["old"], record["review"], in_file_context, review_info)
            _, think_for_in_file_context_summary, in_file_context_summary = model.get_full_deepseek_response(prompt_for_in_file_context_summary)
            in_file_context_summary = self.get_json_value_string(in_file_context_summary, "Summary")
            self.in_file_context_summary = in_file_context_summary

        # #再运行一次refinement作为turn4的结果,此结果中已包含In-file context
        # self.turn, turn = 4, 4
        # results.append({"turn": 4, "result_json": "", "prompt_for_instruction": [], "flag_for_context_change": "",  "ablation_results": [
        #     self.get_refinement_result(), 
        #     self.get_refinement_result(llm="deepseek"),
        #     self.get_refinement_result(llm="deepseek_r1")
        #     ]})

        #1.2 处理Cross-file context
        # if cross_file_context_required == "1":
        if True:
            definitions = contextGenerator.get_repo_context()
            #3.2 Summary Cross-file context
            prompt_for_cross_file_context_summary = model.prompt_for_cross_file_context_summary_without_question(record["old"], record["review"], definitions, review_info)
            _, think_for_cross_file_context_summary, cross_file_context_summary = model.get_full_deepseek_response(prompt_for_cross_file_context_summary)
            cross_file_context_summary = self.get_json_value_string(cross_file_context_summary, "Summary")
            self.cross_file_context_summary = cross_file_context_summary

            self.turn = turn = 4
            results.append({"turn": 4, "result_json": "", "prompt_for_instruction": [], "flag_for_context_change": "",  "ablation_results": [
                self.get_refinement_result(prompt_type="cross-file-context"), 
                # self.get_refinement_result(llm="deepseek"), 
                self.get_refinement_result(prompt_type="cross-file-context", llm="deepseek_r1")]
            })   
        record["definitions"], record["results"] = "omitted", results
        
        print(f"Successfully processed record {record['_id']}")
        self.log_processed_record(record["_id"])
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
        "dataset_path": '/data/DataLACP/wangke/recorebench/result/dataset/RecoreBench.json',
        "output_path": '/data/DataLACP/wangke/recorebench/result/1.0/rq1_0.json',
        # "record_path": '/mnt/ssd2/wangke/dataset/AgentRefiner/_tmp_result.json',
        "log_path": '/data/DataLACP/wangke/recorebench/result/1.0/log.txt'
    }

    print("开始等待")
    # time.sleep(2700)
    print("开始处理数据集")

    # 继续处理未完成的记录
    try:
        with open(config["log_path"], "r", encoding="utf-8") as f:
            ids = [line.strip() for line in f]
    except FileNotFoundError:
        _records = []
        ids = []

    # 被占用的repos
    occupied_repos = []
    
    # 读取数据集
    with open(config["dataset_path"], "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
        #随机打乱顺序
        random.shuffle(records)
        # records = json.load(f)
        # records = [record for record in records if record["repo"] not in occupied_repos]
        # records = records[:10]
        records = [record for record in records if record["_id"] not in ids]
        # records = records[:3000]
        # fileterd by model
        # records = [record for record in records if record["dataset_valid_or_discard_estimation"]["Classification"] == "Valid"]
        print(f"待处理记录数: {len(records)}")

    # 测试单个记录
    # config["output_path"] = '/mnt/ssd2/wangke/dataset/AgentRefiner/tmp_result.json'
    # record = [record for record in records if record["_id"] == 6]
    # record = [records[900]]
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