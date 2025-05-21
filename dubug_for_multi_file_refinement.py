from getProjectCommitState import get_comment_info
from getProjectCommitState import check_CR_CRN_data
from ContextGenerators.LanguageContextGeneratorManager import LanguageContextGenerator
import json
import traceback
from getProjectCommitState import CLBPP, get_commit_details, apply_patch, get_commit_info
from utils.RequestGitHub import RequestGitHub

config = {
    "dataset_path": "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_datasets_all_2.json",
    "output_path" : "/mnt/ssd2/wangke/dataset/AgentRefiner/debug_for_multi_file_refinement.json"
}
requestGitHub = RequestGitHub()

with open(config["dataset_path"], "r") as f, open(config["output_path"], "w") as f1:
    records = [json.loads(line) for line in f]
    for record in records:
        try:
            paths_str, _ = get_commit_details(record["repo"], record["commit_url"])
            lang_flag = False
            for path in paths_str.split('\n'):
                if path.endswith('.py'):
                    lang_flag = True
                    break
            if not lang_flag:
                raise Exception("Unsupported file type")
            
            record = CLBPP(record)

            record["old"] = '\n'.join(record["old"].split('\n'))
            record["new"] = '\n'.join(record["new"].split('\n'))
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
            file_context_backup = file_content.copy()
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
            if not new_added_identifiers_definition_strict : raise Exception("No new added identifiers definition strict found")
            for identifier in new_identifiers:
                if identifier not in old_identifiers:
                    if record["review"].find(identifier) == -1: new_added_identifiers_review_strict.append(identifier)
                    if identifier in precise_definitions_names:
                        if contextGenerator.check_identifier_valid(identifier): new_added_identifiers_definition_strict.append(identifier)
                    new_added_identifiers.append(identifier)
            
            #恢复
            with open(file_path, 'w', encoding='utf-8') as file:
                file.writelines(file_context_backup)

            commit_url = record["commit_url"]
            commit_hash = commit_url.split('/')[-1]
            commit_info = get_commit_info(record["repo"], commit_hash)
            repo = record["repo"]
            repo_path = f"/mnt/ssd2/wangke/CR_data/repo/{repo.split('/')[1]}"
            files = commit_info.get('files', [])
            for file_info in files:
                try:
                    apply_patch(repo_path, file_info)
                    print(f"Applied patch for {file_info['filename']} commit_info:{commit_info['sha']}")
                except:
                    print(f"Error,failed to apply patch for {file_info['filename']} commit_info:{commit_info['sha']}")
                    traceback.print_exc()
            
            valid_new_added_identifiers_with_full_patch = []
            for identifier in new_added_identifiers_definition_strict:
                if contextGenerator.check_identifier_valid(identifier):
                    valid_new_added_identifiers_with_full_patch.append(identifier)
                    print(f"Identifier {identifier} is now valid in {file_path}")
                else:
                    print(f"Identifier {identifier} is still invalid in {file_path}")

            if len(valid_new_added_identifiers_with_full_patch) > 0:
                record["old_identifiers"] = old_identifiers
                record["new_identifiers"] = new_identifiers
                record["new_added_identifiers"] = new_added_identifiers
                record["new_added_identifiers_review_strict"] = new_added_identifiers_review_strict
                record["new_added_identifiers_definition_strict"] = new_added_identifiers_definition_strict
                record["valid_new_added_identifiers_with_full_patch"] = valid_new_added_identifiers_with_full_patch
                f1.write(json.dumps(record, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"Error processing record {record['commit_url']}: {e}")
            traceback.print_exc()


            

            
            

