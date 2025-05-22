import gradio as gr
import json
import os
import re
import copy

# 文件路径
# data_file = "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_datasets_all_filtered_5.json"
# output_file = "/mnt/ssd2/wangke/dataset/AgentRefiner/final_datasets/datasets_human_filtered.json"
data_file = "/mnt/ssd2/wangke/dataset/AgentRefiner/final_datasets/preprocessed_datasets_2.json"
output_file = "/mnt/ssd2/wangke/dataset/AgentRefiner/final_datasets/datasets_human_filtered_4.json"

# 读取数据
with open(data_file, "r", encoding="utf-8") as f:
    all_records = [json.loads(line) for line in f]

print(f"Total {len(all_records)} records.")
review_urls = set()
commit_urls = set()
_records = []
for record in all_records:
    if record["review_url"] not in review_urls:
        _records.append(record)
        review_urls.add(record["review_url"])
print(f"review_url过滤: {len(_records)}")
records = _records
_records = []
for record in records:
    if record["commit_url"] not in commit_urls:
        _records.append(record)
        commit_urls.add(record["commit_url"])
print(f"commit_url过滤: {len(_records)}")
records = _records

# 获取最后一个已通过记录的 _id
passed_records = []
last_passed_id = 0
if os.path.exists(output_file):
    with open(output_file, "r", encoding="utf-8") as f1:
        # passed_records = [json.loads(line) for line in f1]
        for line in f1:
            try:
                record = json.loads(line)
                passed_records.append(record)
            except:
                print(line)
        if passed_records:
            last_passed_id = passed_records[-1].get("_id", 0)

# 根据 last_passed_id 筛选出待审查记录
records_to_review = [r for r in records if r.get("_id", 0) > last_passed_id]

# 使用 index 来跟踪当前展示位置
index = 0

def split_diff(diff):
    diff_lines = diff.split("\n")[1:]
    old_lines = []
    new_lines = []
    for line in diff_lines:
        if line.startswith("-"):
            old_lines.append(line)
        elif line.startswith("+"):
            new_lines.append(line)
        else:
            old_lines.append(line)
            new_lines.append(line)
    return old_lines, new_lines

def review_line_exist_in_old(old_lines, review_line):
    def normalize_text(text):
        text = re.sub(r'\W+','', text)
        return text

    old_lines = [normalize_text(line) for line in old_lines]
    review_line = normalize_text(review_line)
    return review_line in old_lines

def show_record():
    global index
    if index >= len(records_to_review):
        return "✅ 所有记录已评估完毕。", f"{len(passed_records)} / {len(records_to_review)}", "", "", "", "", ""
    record = copy.deepcopy(records_to_review[index])
    record["old"] = record["old"].split("\n")
    record["new"] = record["new"].split("\n")
    record["diff_hunk"] = record["diff_hunk"].split("\n")
    
    # 显示相关信息
    review = record.get("review", "无")
    diff_hunk = "\n".join(record["diff_hunk"])
    review_position_line = record["comment"].get("review_position_line", "未知")
    record_NIDS = ','.join(record.get("new_added_identifiers_definition_strict", []))
    
    if not review_line_exist_in_old(record["old"], review_position_line):
        reject_record()

    record["path"] = "omit"
    record["code_diff"] = "omit"
    
    record_content = json.dumps(record, ensure_ascii=False, indent=2)
    
    # 显示进度
    progress = f"{index + 1} / {len(records_to_review)} Processed: {len(passed_records)}"

    return progress, review, diff_hunk, review_position_line, record_NIDS, record_content

def pass_record():
    global index
    if index >= len(records_to_review):
        return "✅ 所有记录已评估完毕。", f"{len(passed_records)} / {len(records_to_review)}", "", "", "", "", ""
    
    record = records_to_review[index]
    
    # old, new = split_diff(record["diff_hunk"])
    # record["old"] = '\n'.join(old)
    # record["new"] = '\n'.join(new)
    
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    index += 1
    passed_records.append(record)
    return show_record()

def reject_record():
    global index
    if index >= len(records_to_review):
        return "✅ 所有记录已评估完毕。", f"{len(passed_records)} / {len(records_to_review)}", "", "", "", "", ""
    index += 1
    return show_record()

def rollback_record():
    global index
    if index > 0:
        index -= 1
    return show_record()

with gr.Blocks() as demo:
    gr.HTML("<h1 style='text-align: center;'>Human Evaluation Web Site</h1>")

    # 创建布局
    with gr.Column():
        progress_display = gr.Textbox(label="Progress", interactive=False, lines=1)
        review_display = gr.Textbox(label="Review", interactive=False, lines=3)
        
        diff_display = gr.Textbox(label="Code Diff", interactive=False, lines=5)
        review_position_display = gr.Textbox(label="Review Position", interactive=False, lines=2)

        record_NIDS_display = gr.Textbox(label="NIDS", interactive=False, lines=1)

        # 按钮
        with gr.Row():
            btn_pass = gr.Button("✅ Pass")
            btn_reject = gr.Button("❌ Reject")
            btn_rollback = gr.Button("⏪ Rollback")

        record_display = gr.Code(label="Current Record", language="json", lines=20)

    
    btn_pass.click(pass_record, outputs=[progress_display, review_display, diff_display, review_position_display, record_NIDS_display, record_display])
    btn_reject.click(reject_record, outputs=[progress_display, review_display, diff_display, review_position_display, record_NIDS_display, record_display])
    btn_rollback.click(rollback_record, outputs=[progress_display, review_display, diff_display, review_position_display, record_NIDS_display, record_display])

    # 初始化内容
    demo.load(show_record, outputs=[progress_display, review_display, diff_display, review_position_display, record_NIDS_display, record_display,])

demo.launch(server_name="0.0.0.0", server_port=7860)
