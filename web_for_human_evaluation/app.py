import gradio as gr
import json
import os
import re
import copy

# 文件路径
data_file = "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_datasets_all_filtered_5.json"
output_file = "/mnt/ssd2/wangke/dataset/AgentRefiner/final_datasets/datasets_human_filtered.json"

# 读取数据
with open(data_file, "r", encoding="utf-8") as f:
    all_records = [json.loads(line) for line in f]

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
records_to_review = [r for r in all_records if r.get("_id", 0) > last_passed_id]

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
    
    suggested_review = record["dataset_valid_or_discard_estimation"].get("new_review", "")
    
    if not review_line_exist_in_old(record["old"], review_position_line):
        reject_record()

    record["path"] = "omit"
    record["code_diff"] = "omit"
    
    record_content = json.dumps(record, ensure_ascii=False, indent=2)
    
    # 显示进度
    progress = f"{index + 1} / {len(records_to_review)} 已处理： {len(passed_records)}"

    return progress, review, diff_hunk, review_position_line, record_content, suggested_review

def pass_record(final_review):
    global index
    if index >= len(records_to_review):
        return "✅ 所有记录已评估完毕。", f"{len(passed_records)} / {len(records_to_review)}", "", "", "", "", ""
    
    record = records_to_review[index]

    # 保存原始 review 到 original_review 字段
    record["original_review"] = record.get("original_review", record["review"])
    
    # 更新 review 为最终选择的内容
    record["review"] = final_review
    
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

with gr.Blocks() as demo:
    gr.Markdown("# 👁️ 人工数据筛选界面")
    
    # 创建布局
    with gr.Column():
        progress_display = gr.Textbox(label="进度", interactive=False, lines=1)
        review_display = gr.Textbox(label="Original Review", interactive=False, lines=3)
        
        # 新增 Suggested Review 编辑框
        suggested_review_display = gr.Textbox(label="Suggested Review", interactive=True, lines=3)
        
        # 用来选择 Original 或 Suggested
        review_choice = gr.Radio(["Original", "Suggested"], label="选择 Review", value="Suggested", interactive=True)
        
        diff_display = gr.Textbox(label="Code Diff", interactive=False, lines=5)
        review_position_display = gr.Textbox(label="评论位置", interactive=False, lines=2)

        # 按钮
        with gr.Row():
            btn_pass = gr.Button("✅ 通过")
            btn_reject = gr.Button("❌ 不通过")

        record_display = gr.Code(label="当前记录内容", language="json", lines=20)

    # 绑定按钮事件
    def update_suggested_review(review_choice):
        # 如果选择 Original，更新 Suggested Review 显示为原始的 review 内容，否则显示 suggested 的内容
        record = records_to_review[index]
        if review_choice == "Original":
            return record.get("review", "无")
        else:
            return record["dataset_valid_or_discard_estimation"].get("new_review", "")

    review_choice.change(update_suggested_review, inputs=review_choice, outputs=suggested_review_display)
    
    btn_pass.click(pass_record, inputs=[suggested_review_display], outputs=[progress_display, review_display, diff_display, review_position_display, record_display, suggested_review_display])
    btn_reject.click(reject_record, outputs=[progress_display, review_display, diff_display, review_position_display, record_display, suggested_review_display])

    # 初始化内容
    demo.load(show_record, outputs=[progress_display, review_display, diff_display, review_position_display, record_display, suggested_review_display])

demo.launch(server_name="0.0.0.0", server_port=7860)
