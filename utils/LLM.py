import os
from transformers import pipeline

# 设置模型的本地缓存路径
model_cache_dir = "/mnt/ssd2/wangke/.cache/deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
os.environ["XDG_CACHE_HOME"] = model_cache_dir
os.environ["TRANSFORMERS_CACHE"] = model_cache_dir
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"  # 设置内存管理优化

# 加载模型并设置生成参数
messages = [
    {"role": "user", "content": "Who are you?"},
]

pipe = pipeline("text-generation", model=model_cache_dir)

# 尝试使用更小的 max_length
response = pipe(messages[0]["content"], max_length=2000)  # 减小最大生成长度
print(response)
