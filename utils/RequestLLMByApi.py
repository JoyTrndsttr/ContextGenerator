from openai import OpenAI
import json

class RequestLLMByApi:
    def __init__(self):
        self.config = {
            "temperature": 0,
        }
    
    def get_deepseek_response(self, prompt, system_prompt = None):
        token = json.load(open("/home/wangke/model/ContextGenerator/settings.json", encoding='utf-8'))["deepseek_r1"]
        client = OpenAI(api_key=token, base_url="https://api.deepseek.com")
        if not system_prompt:
            response = client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                **self.config
            )
        else:
            response = client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                **self.config
            )
        text = response.choices[0].message.content
        # output = text.split("</think>")[1]
        # think = text.split("</think>")[0]
        # return output, think
        return text
    
    def prompt_for_estimate_dataset(self, code_diff, review, review_line, NIDS):
        prompt = "假如你是一个评估员，你需要判断一条代码评审任务的数据是否合格。\n"
        prompt += f"在这个任务中，评审员在{review_line}这一行评论了：{review}\n"
        prompt += f"开发者所做的代码变更为:{code_diff}\n"
        prompt += f"比较关键的变更(NIDS)为:{','.join(NIDS)}\n"
        prompt += f"所谓OriginalCode为CodeDiff中未改变的行和以'-'开头的行，而RevisedCode/GroundTruth为CodeDiff中未改变的行和以'+'开头的行\n"
        prompt += f"假设有一个能查询仓库上下文的自动化代码评审工具，它需要根据review和OriginalCode生成PredictCode，这个PredictCode和RevisedCode越相似评估分数越高。但是这个任务很难，需要从仓库中检索信息，比如OriginalCode所在文件的其他代码如何实现的，它还能查询它目前关注的代码中一些函数的定义。\n"
        prompt += f"从OriginalCode到RevisedCode有一些增加的标识符(称为NIDS)，它们是在Repository中定义的函数，没有拿到这个信息，它不可能能够预测出与RevisedCode相同的代码。这条数据合格的条件是，review引发了修改，review和CodeDiff有直接关系，从review和OriginalCode出发，有希望能够预测出所有的NIDS。否则不合格。\n"
        prompt += f"你需要首先给出你的判断，合格/不合格。假如不合格，给出简短的理由。假如合格，先详细解释Review是什么意思，每个Diff的修改对应Review的哪一句话，然后给出NIDS的预测思路，并总结为什么合格。\n"
        return prompt

if __name__ == "__main__":
    prompt = "What is the capital of France?"
    request_llm = RequestLLMByApi()
    output, think = request_llm.get_deepseek_response(prompt)
    print(output)
    print(think)
    pass