import json
import model
from ContextGenerators.LanguageContextGeneratorManager import LanguageContextGenerator
from getProjectCommitState import CLBPP
import re
import traceback
config = {
    "dataset_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_datasets_first4w.json",
    "output_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_datasets_all_filtered_3.json",
    "log_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/log.json"
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

    # 应用ground truth补丁
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
            if identifier in precise_definitions_names:
                if contextGenerator.check_identifier_valid(identifier): new_added_identifiers_definition_strict.append(identifier)
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

def filtered_by_relationship_between_diff_and_review_with_LLMs(record):
    old, review, new = record["old"], record["review"], record["new"]
    prompt_for_dataset_valid_or_discard_estimation = model.prompt_for_dataset_valid_or_discard_estimation(old, review, new)
    _, think_for_dataset_valid_or_discard_estimation, dataset_valid_or_discard_estimation_result_json = model.get_full_deepseek_response(prompt_for_dataset_valid_or_discard_estimation)
    record["dataset_valid_or_discard_estimation"] = {
        "Classification": get_json_value_string(dataset_valid_or_discard_estimation_result_json, "Classification"),
        "Reason": get_json_value_string(dataset_valid_or_discard_estimation_result_json, "Reason"),
        "Think_for_dataset_valid_or_discard_estimation": think_for_dataset_valid_or_discard_estimation.split('\n')
    }
    record["valid_or_discard"] = "valid" if record["dataset_valid_or_discard_estimation"]["Classification"].find("Valid") != -1 else "discard"
    return record

def filtered_by_huristics_approaches(record):
    if record["review"].find("```") != -1: raise Exception("Review contains code block")
    if record["review"].find("suggestion") != -1: raise Exception("Review contains suggestion")
    if not (record["new_added_identifiers_review_strict"] and record["new_added_identifiers_definition_strict"]): raise Exception("No new strictlyadded identifiers")
    return record

with open(config['log_path'], 'r') as f00:
    count = json.load(f00)

with open(config['output_path'], 'a') as f0:
    with open(config['dataset_path'], 'r') as f:
        records = [json.loads(line) for line in f]
        records = records[18193:]
        # records = [records[10]]
        # records = json.load(f)
        # records = [record for record in records if record["_id"]==197]
        if not count:
            count = {
                "Total": len(records),
                "Successful_processed": 0,
                "No_new_identifier_found": 0,
                "Low_quality_sample": 0,
                "No_new_strictlyadded_identifiers": 0,
            }
        for record in records:
            #将count的信息写入文件
            with open(config['log_path'], 'w') as f1:
                count_str_keys = {str(k): v for k, v in count.items()}
                json.dump(count_str_keys, f1, indent=4)
            print(f"Processing {record['_id']}")
            count["Total"] += 1
            try:
                pre_filtered_record = filter_record_by_new_identifier(record)
                if not pre_filtered_record: 
                    print(f"No new identifier found in {record['_id']}")
                    count["No_new_identifier_found"] += 1
                    continue
                filtered_record = filtered_by_relationship_between_diff_and_review_with_LLMs(record)
                if not filtered_record: 
                    print(f"Low quality sample for {record['_id']}")
                    count["Low_quality_sample"] += 1
                    continue
                strictly_filtered_record = filtered_by_huristics_approaches(filtered_record)
                if not strictly_filtered_record: 
                    print(f"No strictly added identifier found in {record['_id']}")
                    count["No_new_strictlyadded_identifiers"] += 1
                    continue
                f0.write(json.dumps(strictly_filtered_record, ensure_ascii=False) + '\n')
                count["Successful_processed"] += 1
            except Exception as e:
                print(f"Error processing {record['_id']}: {e}")
                try:
                    key = e.args[0]
                except: key = "Others"
                count[key] = count.get(key, 0) + 1
                traceback.print_exc()