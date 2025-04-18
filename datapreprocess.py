import json
import model
from AgentRefiner import AgentRefiner
from getProjectCommitState import get_comment_info
from ContextGenerators.LanguageContextGeneratorManager import LanguageContextGenerator
import getProjectCommitState
from getProjectCommitState import CLBPP
import re
import traceback
# config = {
#     "dataset_path": "/mnt/ssd2/wangke/dataset/datasets.json",
#     "output_path": '/mnt/ssd2/wangke/dataset/map_result/',
#     "record_path": '/mnt/ssd2/wangke/dataset/map_result/llama_map.json',
#     "result_path": '/mnt/ssd2/wangke/dataset/map_result/llama_result.json'
# }
# config = {
#     "dataset_path": "/mnt/ssd2/wangke/CR_data/dataset/map_result/dataset_sorted_llama.json",
#     "output_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/CR_and_CRN_4_6.json"
# }
config = {
    "dataset_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_repo_datasets.json",
    "output_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_repo_datasets_filtered.json"
}

def get_json_value_number(str, key):
    try:
        return re.search(r'(\d+)', str.split(key)[1]).group(0)
    except:
        return "0"

def get_json_value_string(str, key):
    try:
        return re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', str).group(1)
    except:
        return ""

def normalize_text(text):
    text = re.sub(r'\W+','', text)
    return text

def filter_record_by_new_identifier(record):
    record = CLBPP(record)
    record["old"] = '\n'.join(record["old"].split('\n')[1:])
    record["new"] = '\n'.join(record["new"].split('\n')[1:])
    languageContextGenerator = LanguageContextGenerator(record)
    contextGenerator = languageContextGenerator.context_generator
    definitions_before_refinement = contextGenerator.node_list
    old_identifiers = [def_bef.text.decode('utf-8') for def_bef in definitions_before_refinement]
    old_identifiers = list(set(old_identifiers))

    diff = contextGenerator.code_diff
    file_path = contextGenerator.file_path
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            file_content = file.readlines()
    except Exception as e:
        print(f"Error processing patch for {file_path}: {e}")
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

    _languageContextGenerator = LanguageContextGenerator(record)
    contextGenerator = _languageContextGenerator.get_context_generator_after_applying_diff()
    definitions_after_patch = contextGenerator.node_list
    new_identifiers = [def_aft.text.decode('utf-8') for def_aft in definitions_after_patch]
    new_identifiers = list(set(new_identifiers))
    precise_definitions = contextGenerator.getContext()
    precise_definitions_names = [def_prec["name"] for def_prec in precise_definitions]

    new_added_identifiers = []
    new_added_identifiers_review_strict = []
    new_added_identifiers_definition_strict = []
    for identifier in new_identifiers:
        if identifier not in old_identifiers:
            if record["review"].find(identifier) == -1: new_added_identifiers_review_strict.append(identifier)
            if identifier in precise_definitions_names: new_added_identifiers_definition_strict.append(identifier)
            new_added_identifiers.append(identifier)
    if new_added_identifiers:
        record["old_identifiers"] = old_identifiers
        record["new_identifiers"] = new_identifiers
        record["new_added_identifiers"] = new_added_identifiers
        record["new_added_identifiers_review_strict"] = new_added_identifiers_review_strict
        record["new_added_identifiers_definition_strict"] = new_added_identifiers_definition_strict
        return record
    else:
        return None

with open(config['output_path'], 'a') as f0:
    with open(config['dataset_path'], 'r') as f:
        records = [json.loads(line) for line in f]
        # records = [records[10]]
        # records = json.load(f)
        # records = [record for record in records if record["_id"]==38]
        for record in records:
            print(f"Processing {record['_id']}")
            try:
                filtered_record = filter_record_by_new_identifier(record)
                if filtered_record:
                    f0.write(json.dumps(filtered_record, ensure_ascii=False) + '\n')
            except Exception as e:
                print(f"Error processing {record['_id']}: {e}")
                traceback.print_exc()
#             try:
#                 print(f"Processing {record['_id']}")

#                 new_line = record["new"].split("\n")
#                 new_line_add_flag = False
#                 for line in new_line:
#                     if line.startswith('+') : new_line_add_flag = True
#                 if not new_line_add_flag: continue
#                 if record["review"].find("```") != -1:continue

#                 if record["review"].find("suggestion") != -1:#含有suggestion的不太可能需要上下文
#                     continue
                
#                 old = record["old"]

#                 comment_info, review_url = get_comment_info(record)
#                 record["comment"] = comment_info
#                 comment = record["comment"]
#                 diff_hunk_lines = comment["diff_hunk"].split('\n')
#                 start = int(re.findall(r'(\d+)', diff_hunk_lines[0])[2])
#                 if comment["original_start_line"] and comment["original_start_line"]-start+1 < len(diff_hunk_lines):
#                     comment["review_hunk_start_line"] = diff_hunk_lines[comment["original_start_line"]-start+1][1:] #加1是因为第一行是code_diff_hunk的prefix
#                 index = len(diff_hunk_lines)-1 # 指向review_position_line
#                 for i in range(index, -1, -1):
#                     line = diff_hunk_lines[i][1:]
#                     if line:
#                         comment["review_position_line"] = line
#                         break

#                 review_line = record["comment"]["review_position_line"]
#                 flag = False
#                 for line in old.split("\n"):
#                     if normalize_text(line) == normalize_text(review_line):
#                         flag = True
#                         break
#                 if not flag: continue

#                 prompt_for_repo_context_dependency_estimation = model.prompt_for_repo_context_dependency_estimation(record["old"], record["review"], record["new"], record["comment"])
#                 _, think_for_repo_context_dependency_estimation, repo_context_dependency_estimation_result_json = model.get_full_deepseek_response(prompt_for_repo_context_dependency_estimation)
#                 record["repo_context_dependency_estimation"] = {
#                     "Additional_context_required": get_json_value_number(repo_context_dependency_estimation_result_json, "Additional_context_required"),
#                     "Reason_for_require_additional_context": get_json_value_string(repo_context_dependency_estimation_result_json, "Reason_for_require_additional_context"),
#                     "Think_for_repo_context_dependency_estimation": think_for_repo_context_dependency_estimation.split('\n')
#                 }

#                 if record["repo_context_dependency_estimation"]["Additional_context_required"] == "0":
#                     continue

#                 if not record["old"].startswith("\n"):
#                     record["old"] = "#" + record["old"]
#                     record["new"] = "#" + record["new"]
#                 record["old"] = [line.strip() for line in record["old"].split("\n") if line.strip()]
#                 record["new"] = [line.strip() for line in record["new"].split("\n") if line.strip()]
#                 f0.write(json.dumps(record, ensure_ascii=False) + '\n')
#             except Exception as e:
#                 print(f"Error processing {record['_id']}: {e}")