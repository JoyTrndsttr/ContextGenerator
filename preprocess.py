import json
import model
from ContextGenerators.LanguageContextGeneratorManager import LanguageContextGenerator
from getProjectCommitState import CLBPP, get_commit_details
import re
import traceback
import time
from multiprocessing import Manager
import multiprocessing as mp
from collections import defaultdict
import os

config = {
    "dataset_path": "/data/DataLACP/wangke/recorebench/java/datasets/new_datasets_java.json",
    "output_path": "/data/DataLACP/wangke/recorebench/java/datasets/preprocessed_datasets.json",
    "log_path": "/data/DataLACP/wangke/recorebench/java/log/log1.json"
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
    # record["old"] = '\n'.join(record["old"].split('\n'))
    # record["new"] = '\n'.join(record["new"].split('\n'))
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
    if not (new_added_identifiers_review_strict and new_added_identifiers_definition_strict): raise Exception("No new strictly added identifiers")
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
        "Think_for_dataset_valid_or_discard_estimation": think_for_dataset_valid_or_discard_estimation.split('\n'),
        "new_review": get_json_value_string(dataset_valid_or_discard_estimation_result_json, "New Review")
    }
    record["valid_or_discard"] = "valid" if record["dataset_valid_or_discard_estimation"]["Classification"].find("Valid") != -1 else "discard"
    return record

def review_line_exist_in_old(old_lines, review_line):
    def normalize_text(text):
        text = re.sub(r'\W+','', text)
        return text

    old_lines = [normalize_text(line) for line in old_lines]
    review_line = normalize_text(review_line)
    return review_line in old_lines

def filtered_by_huristics_approaches(record):
    if record["review"].find("```") != -1: raise Exception("Review contains code block")
    if record["review"].find("suggestion") != -1: raise Exception("Review contains suggestion")
    if len([line for line in record["new"].split('\n') if line.startswith("+")]) >= 6: raise Exception("Too many added lines")
    if not review_line_exist_in_old(record["old"].split('\n'), record["comment"]["review_position_line"]) : raise Exception("Review position line not in old code")
    return record

def check_dataset_valid(record):
    try:
        huristically_filtered_record = filtered_by_huristics_approaches(record)
        if not huristically_filtered_record: 
            print(f"No strictly added identifier found in {record['_id']}")
            return "No_new_strictlyadded_identifiers"
        pre_filtered_record = filter_record_by_new_identifier(huristically_filtered_record)
        if not pre_filtered_record: 
            print(f"No new identifier found in {record['_id']}")
            return "No_new_identifier_found"
        llm_filtered_record = filtered_by_relationship_between_diff_and_review_with_LLMs(pre_filtered_record)
        if not llm_filtered_record: 
            print(f"Low quality sample for {record['_id']}")
            return "Low_quality_sample"
        with open(config['output_path'], 'a') as f0:
            f0.write(json.dumps(llm_filtered_record, ensure_ascii=False) + '\n')
        print(f"Saved {record['_id']}")
        return "Successful_processed"
    except Exception as e:
        print(f"Error processing {record['_id']}: {e}")
        traceback.print_exc()
        try:
            key = e.args[0]
            return key
        except: return "Others"

def store_to_log_file(keys, lock):
    with lock:
        for i in range(5):
            print(f"第{i+1}次尝试存储日志文件")
            try:
                with open(config['log_path'], 'r') as f00:
                    count = json.load(f00)
                for key in keys:
                    count["Total"] = count.get("Total", 0) + 1
                    count[str(key)] = count.get(key, 0) + 1
                with open(config['log_path'], 'w') as f00:
                    json.dump(count, f00, indent=4)
                    f00.flush()
                    os.fsync(f00.fileno())
                return True
            except Exception as e:
                print("Warning: Error reading the log file, try again")
                traceback.print_exc()
                time.sleep(10)
        return False
    
def process_repos(records, lock):
    repo = records[0]["repo"]
    print(f"Processing {repo}: {len(records)} records")
    keys = []
    for record in records:
        key = check_dataset_valid(record)
        print(f"Processed {record['_id']}: {key}")
        keys.append(key)
    flag = store_to_log_file(keys, lock)
    if not flag: print(f"Warning: Failed to store log file for {repo}")
    print(f"Processed {repo}: {len(records)} records")

def get_last_processed_id():
    try:
        with open(config['log_path'], 'r') as f00:
            count = json.load(f00)
        return count["Total"]
    except:
        return 0

turn = 0
while True:
    turn += 1
    print(f"Start for turn {turn}")
    with open(config['dataset_path'], 'r') as f:
        records = [json.loads(line) for line in f]

        records = [record for record in records if record["_id"] == 19564]
        process_repos(records, None)
        break

        last_processed_id = get_last_processed_id()
        if last_processed_id >= len(records):
            print(f"All records have been processed")
            time.sleep(3600)
            continue
        else: records = records[last_processed_id:]
        repo_map = defaultdict(list)
        for record in records:
            repo_map[record["repo"]].append(record)
        with mp.Pool(processes=13) as pool:
            with Manager() as manager:
                lock = manager.Lock()
                tasks = [(records, lock) for records in repo_map.values()]
                pool.starmap(process_repos, tasks)
    print(f"End for turn {turn}")
    time.sleep(3600)