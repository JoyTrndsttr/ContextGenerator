import json
from ContextGenerators.LanguageContextGeneratorManager import LanguageContextGenerator
import getProjectCommitState
from getProjectCommitState import CLBPP
import model

def merge_diff(old, new):
    diff = []
    i, j = 0, 0
    while i < len(old) or j < len(new):
        line_old = old[i] if i < len(old) else ""
        line_new = new[j] if j < len(new) else ""

        if line_old.startswith("-"):
            diff.append(line_old)
            i += 1
        elif line_new.startswith("+"):
            diff.append(line_new)
            j += 1
        else:
            # Prefer new line if available and not a + line
            if j < len(new) and not line_new.startswith("+"):
                diff.append(line_new)
            elif i < len(old):
                diff.append(line_old)
            i += 1
            j += 1

    return diff

config = {
    # "dataset_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_repo_datasets_estimated.json",
    "dataset_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_repo_datasets.json",
    #  "dataset_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_datasets.json",
    "output_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/tmp_result.json"
}
with open(config["dataset_path"], "r") as f:
    records = [json.loads(line) for line in f]
    print(len(records))
    # print(records[5]["_id"])
    record = records[12724]
    old_lines = record["old"].split("\n")
    new_lines = record["new"].split("\n")
    record = CLBPP(record)
    languageContextGenerator = LanguageContextGenerator(record)
    contextGenerator = languageContextGenerator.context_generator
    defs_bef = contextGenerator.node_list


    diff = contextGenerator.code_diff
    file_path = contextGenerator.file_path
    repo = record["repo"]
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
    contextGenerator = _languageContextGenerator.context_generator
    defs_aft = contextGenerator.node_list

    print([def_bef.text.decode('utf-8') for def_bef in defs_bef])
    print([defs_aft.text.decode('utf-8') for defs_aft in defs_aft])





        
    




    print(defs_bef)

    


# with open(config["output_path"], "w") as f1:
#     json.dump(record, f1, indent=4)