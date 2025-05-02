import gradio as gr
import json
import os

# 文件路径
data_file = "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_datasets_filtered_first1k.json"
output_file = "/mnt/ssd2/wangke/dataset/AgentRefiner/datasets/new_datasets_human_filtered.json"

# 读取数据
with open(data_file, "r", encoding="utf-8") as f:
    all_records = [json.loads(line) for line in f]

# 获取最后一个已通过记录的 _id
passed_records = []
last_passed_id = 0
if os.path.exists(output_file):
    with open(output_file, "r", encoding="utf-8") as f1:
        passed_records = [json.loads(line) for line in f1]
        if passed_records:
            last_passed_id = passed_records[-1].get("_id", 0)

# 根据 last_passed_id 筛选出待审查记录
records_to_review = [r for r in all_records if r.get("_id", 0) > last_passed_id]
records_to_review = [record for record in records_to_review if record["dataset_valid_or_discard_estimation"]["Classification"] = "Valid"]

# 使用 index 来跟踪当前展示位置
index = 0

def show_record():
    global index
    if index >= len(records_to_review):
        return "✅ 所有记录已评估完毕。", f"{len(passed_records)} / {len(all_records)}"
    record = records_to_review[index]
    record["old"] = record["old"].split("\n")
    record["new"] = record["new"].split("\n")
    record["diff_hunk"] = record["diff_hunk"].split("\n")
    record["path"] = "omit"
    record["code_diff"] = "omit"
    # 使用json.dumps来格式化输出，并且确保输出格式正确
    return json.dumps(record, ensure_ascii=False, indent=2), f"{len(passed_records)} / {len(all_records)}"

def pass_record():
    global index
    if index >= len(records_to_review):
        return "✅ 所有记录已评估完毕。", f"{len(passed_records)} / {len(all_records)}"
    record = records_to_review[index]
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    index += 1
    passed_records.append(record)
    return show_record()

def reject_record():
    global index
    if index >= len(records_to_review):
        return "✅ 所有记录已评估完毕。", f"{len(passed_records)} / {len(all_records)}"
    index += 1
    return show_record()

with gr.Blocks() as demo:
    gr.Markdown("# 👁️ 人工数据筛选界面")
    # 使用 gr.Code 组件来显示 JSON 格式的内容并高亮
    record_display = gr.Code(label="当前记录内容", language="json", lines=20)
    progress_display = gr.Textbox(label="进度")
    with gr.Row():
        btn_pass = gr.Button("✅ 通过")
        btn_reject = gr.Button("❌ 不通过")
    btn_pass.click(pass_record, outputs=[record_display, progress_display])
    btn_reject.click(reject_record, outputs=[record_display, progress_display])

    # 初始化内容
    demo.load(show_record, outputs=[record_display, progress_display])

demo.launch(server_name="0.0.0.0", server_port=7860)
