# 数据库连接配置
from time import sleep
import json
from openai import OpenAI
from evaluation import myeval
from utils.RequestModel import OpenAIUtils
import re
import logging

generation_kwargs = {
    "max_tokens": 1000,
    "temperature": 0,
    "top_p": 0.95,
    "n": 1,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0
}

model = OpenAIUtils(model_id="llama:7b", generation_kwargs=generation_kwargs)
logging.basicConfig(filename='log.txt', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

def prompt_for_classifier(old, review, new):
    prompt = "\nYou are a experienced researcher majoring in code review tasks. In a pull request, you discover that there are senarios where the the review is not related to the code changes. Additionally, a developer should modify the code based on the review in a code refinement task. When he/she encounters a identifier of which he/she forgets the utility, he/she would search its usage in the repository. You should tell if this context is need to correctly modify the code based on the review."
    prompt += "\nTo evaluate the relevance between the review and code diff, as well as the extent of the context dependency, you should provide a \'Relevance Score\' and a \'Context Dependency Score\' each ranging from 0 to 10 and explain the reason behind the score. Here are some examples."
    prompt += "\nSample1:"
    prompt += "\nold code:```\n def name_to_sphinx(self):\n class OpReference:\n-    def __init__(self, operator, docstring, order = None):\n         self.docstring = docstring\n         self.order = 1000000 if order is None else order\n```"
    prompt += "\nnew code:```\n def name_to_sphinx(self):\n class OpReference:\n+    def __init__(self, operator, docstring, order=None):         self.operator = operator\n         self.docstring = docstring\n         self.order = 1000000 if order is None else order\n```"
    prompt += "\nreview: Unfortunately, Python has infinite integers and sorting by key (instead of compare function)."
    prompt += "\nanswer:{\"Relevance Score\": 0, \"Context Dependency Score\": 7, \"Explanation\": \"The only change in the code is removing an extra space around the '=' in the function parameter 'order = None', making it 'order=None'. This is purely a formatting change and has no relevance to the review content, so the Relevance Score is 0. Althouth the line 'self.order = 1000000' is related to the concept of 'infinite integers' mentioned in the review, the \'compare function\' is unclear for the code refinement, leading to a Context Dependency Score of 7.\"}"
    prompt += "\nSample2:"
    prompt += "\nold code:```\n             msg_aggregator=self.msg_aggregator,\n         )\n-    def _initialize_uniswap(self, premium: Optional[Premium]) -> None:\n-        self.eth_modules[\'uniswap\'] = Uniswap(\n-            ethereum_manager=self.ethereum,\n-            database=self.database,\n-            premium=premium,\n-            msg_aggregator=self.msg_aggregator,\n-        )\n \n     def get_zerion(self) -> Zerion:\n         \"\"\"Returns the initialized zerion. If it\'s not ready it waits for 5 seconds\n         and then times out. This should really never happen\n```"
    prompt += "\nnew code:```\n             msg_aggregator=self.msg_aggregator,\n         )\n \n     def get_zerion(self) -> Zerion:\n         \"\"\"Returns the initialized zerion. If it\'s not ready it waits for 5 seconds\n         and then times out. This should really never happen\n```"
    prompt += "\nThe reviewer commented on the line:```def _initialize_uniswap(self, premium: Optional[Premium]) -> None:``` :so this is not needed"
    prompt += "\nanswer:{\"Relevance Score\": 10, \"Context Dependency Score\": 0, \"Explanation\":\"The modification perfectly perform the required deletion based on the review, so the Relevance Score is 10. Additionally, the only required change is removing the function \'_initialize_uniswap\'. Since how to refine the code is clear, additional context would provide minimal extra value for code refinement, leading to a Context Dependency Score of 0.\"}"
    prompt += "\nSample3:"
    prompt += "\nold code:```\n import typing\n from mitmproxy.contentviews import base\n-from mitmproxy.contentviews.json import parse_json\n \n \n-PARSE_ERROR = object()\n def format_graphql(data):\n```"
    prompt += "\nnew code:```\n import typing\n from mitmproxy.contentviews import base\n+from mitmproxy.contentviews.json import parse_json, PARSE_ERROR\n \n \n def format_graphql(data):\n```"
    prompt += "\nreview: \'PARSE_ERROR\' should be imported and not redefined here, or am I missing something?"
    prompt += "\nanswer:{\"Relevance Score\": 10, \"Context Dependency Score\": 10, \"Explanation\":\"The modification perfectly imports the \'PARSE_ERROR\' object based on the review, so the Relevance Score is 10. Additionally, it's unclear how to import the \'PARSE_ERROR\' object. However, the context about the implementation of the \'parse_json\' function may help to understant the utility of the \'PARSE_ERROR\' object, so the Context Dependency Score is 10.\"}"
    prompt += "\nHere is a new sample, please provide a \'Relevance Score\' and a \'Context Dependency Score\' each ranging from 0 to 10 and explain the reason behind the score. Your answer should be in the format of a JSON object:```{ \"Relevance Score\": <Relevance Score>, \"Context Dependency Score\": <Context Dependency Score>, \"Explanation\": \"<Explanation>\" }```"
    prompt += f"\nold code: \n```\n{old}\n```"
    prompt += f"\nnew code: \n```\n{new}\n```"
    prompt += f"\nreview: {review}"
    return prompt

def prompt_for_instruction(old_without_minus, review, calls, review_info, name_list):
    prompt = "As a developer, your pull request receives a reviewer's comment on " \
              "a specific piece of code that requires a change.In order to make " \
              "changes based on the review,you need to refer back to the original code. " \
              "You should provide the code implementation of which function you'd most "\
              "like to refer to.\n"
    prompt += "The old code being referred to in the hunk of code changes is:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else: prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review
    if len(calls) > 0:
        prompt += "\nBased on the review, you checked the source code and find that :"
        for call in calls:
            caller, callee, callee_text, callee_context = call
            callee_text_list = callee_text.split('\n')
            if len(callee_text_list) > 20:
                concise_callee_text = ""
                concise_callee_text += callee_text_list[0] + "\n"
                for callee_text_line in callee_text_list[1:]:
                    if callee_text_line.find("def") != -1 :
                        concise_callee_text += callee_text_line + "\n"
            if caller == callee or caller == "default_function": 
                if len(callee_text_list) > 20:
                    prompt += f"\nThe concise definition of \n{callee} is:\n```\n{concise_callee_text}\n``` "
                else:
                    prompt += f"\n{callee} is defined as:\n```\n{callee_text}\n```"
            else :
                if len(callee_text_list) > 20:
                    prompt += f"\n{caller} calls {callee}, and the concise definition of {callee} is:\n```\n{concise_callee_text}\n``` "
                else:
                    prompt += f"\n{caller} calls {callee} which is defined as:\n```\n{callee_text}\n```"
    if len(name_list) > 0:
        name_str = "Notify the following functions have been checked:"
        for name in name_list:
            name_str += f"{name}, "
        prompt += f"\n{name_str[:-2]}"
    prompt += "\nPlease provide the name appears in the source code that have not yet been checked and explain why you chose it. Format your response"\
              " as a JSON object:```{ \"function_name\": \"<function_name>\", \"reason\": \"<reason>\" }```"
    return prompt

def prompt_for_refinement(old_without_minus, review, calls, review_info, with_summary_or_code, with_presice_review_position, clipped_flag):
    prompt = ""
    prompt += "As a developer, imagine you've submitted a pull request and" \
              " your team leader requests you to make a change to a piece of code." \
              " The old code being referred to in the hunk of code changes is:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    if not with_presice_review_position or not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else: prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review
    if len(calls) > 0:
        prompt += "\nBased on the review, you checked the source code and find that :"
        for call in calls:
            caller, callee, callee_text, callee_context = call
            callee_text_list = callee_text.split('\n')
            if len(callee_text_list) > 20:
                concise_callee_text = '\n'.join(callee_text_list[:20])
            match = re.match(r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)\s*:.*$', callee_text_list[0])
            signature = f"{match.group(1)}({match.group(2)})" if match else callee
            main_purpose = callee_context.split('Summary:')
            main_purpose = main_purpose[1].strip() if len(main_purpose) > 1 else callee_context
            
            if caller == callee or caller == "default_function": 
                if with_summary_or_code == 'code':
                    if len(callee_text_list) > 20:
                        prompt += f"\nThe first 20 lines of {signature} are implemented as follows:\n```\n{concise_callee_text}\n``` "
                    else:
                        prompt += f"\n{signature} is defined as:\n```\n{callee_text}\n```"
                elif with_summary_or_code =='summary':
                    prompt += f"\nThe detail information of {signature} is: \n{main_purpose}"
            else :
                if with_summary_or_code == 'code':
                    if len(callee_text_list) > 20:
                        prompt += f"\n{caller} calls {signature}, and the first 20 lines of {signature} are implemented as follows:\n```\n{concise_callee_text}\n``` "
                    else:
                        prompt += f"\n{caller} calls {signature} which is defined as:\n```\n{callee_text}\n```"
                elif with_summary_or_code =='summary':
                    prompt += f"\n{caller} calls {signature}, and the detail information of {signature} is: \n{main_purpose}"
    prompt += "\nPlease generate the revised code according to the review. " \
              "Please ensure that the revised code follows the original code format" \
              " and comments, unless it is explicitly required by the review."
    if clipped_flag:
        line_start = old_without_minus.split("\n")[0]
        if line_start.strip() == "": line_start = old_without_minus.split("\n")[1]
        line_end = old_without_minus.split("\n")[-1]
        prompt += f"Specifically,if not required by the review, your code should start with:\"{line_start}\" and end with:\"{line_end}\""
    return prompt

def prompt_for_context(text):
    prompt = ""
    # prompt += "Try to summarize the class or function about the following text, your summary should include the"\
    #           " function signature, parameters, return type, and main purpose with no more than 100 words."\
    #           "format your response as:\nSignature and Parameters: <function_signature>\nReturn Type:"\
    #           " <return_type>\nMain Purpose: <purpose>\n"
    prompt += "Try to summarize the class or function about the following text, your summary should include at least"\
              " the return type and main purpose with no more than 100 words."\
              "format your response as Summary: <Your Summary>\n"
    prompt += "```\n{}\n```\n".format(text)
    return prompt

def get_model_response(prompt,temperature=1.0):
    answer = model.get_completion([prompt])
    result = re.search(r'```(.*)```', answer,re.DOTALL)
    print(f"prompt:\n{prompt}\nanswer:\n{answer}")
    if result: # TODO 由于模型可能会受到提示词的干扰，应该选表现最好的newcode
        newcode = result.group(1)
    return newcode if result else "", answer

def calc_em_and_bleu(new, new_code):
    new_without_plus = remove_prefix(new)
    gpt_em, gpt_em_trim, _, _, gpt_bleu, gpt_bleu_trim \
        = myeval(new_without_plus, new_code)
    return gpt_em, gpt_em_trim, gpt_bleu, gpt_bleu_trim

def evaluate(id, prompt, new, type):
    def calc_em_and_bleu(gpt_code, gpt_answer):
        new_code = []
        for line in new.split("\n"):
            if line.strip() != "":
                new_code.append(line[1:].strip())
        new_code = "\n".join(new_code)
        gpt_em, gpt_em_trim, _, _, gpt_bleu, gpt_bleu_trim \
            = myeval(new_code, gpt_code)
        return gpt_em, gpt_em_trim, gpt_bleu, gpt_bleu_trim
    
    logging.info(f'id:\n {id}')
    print(prompt)
    logging.info(f'Prompt:\n {prompt}')
    i = 0
    gpt_code, gpt_answer = get_model_response(prompt)
    gpt_em, gpt_em_trim, gpt_bleu, gpt_bleu_trim = calc_em_and_bleu(gpt_code, gpt_answer)
    max = gpt_bleu + gpt_bleu_trim
    while i < 2:
        code, answer = get_model_response(prompt)
        em, em_trim, bleu, bleu_trim = calc_em_and_bleu(code, answer)
        tmp = bleu + bleu_trim
        if tmp > max:
            gpt_em, gpt_em_trim, gpt_bleu, gpt_bleu_trim = calc_em_and_bleu(code, answer)
            gpt_code, gpt_answer = code, answer
        i += 1
    logging.info(f'Answer:\n {gpt_answer}')
    print(f"{gpt_em}, {gpt_em_trim}, _, _, {gpt_bleu}, {gpt_bleu_trim}")
    logging.info(f"{gpt_em}, {gpt_em_trim}, _, _, {gpt_bleu}, {gpt_bleu_trim}")
    store_result(id, gpt_em, gpt_em_trim, gpt_bleu, gpt_bleu_trim, type)

def remove_prefix(old):
    old_without_minus = [] #去除第一个符号
    for line in old.split("\n"):
        if line.strip() != "":
            old_without_minus.append(line[1:])
    return "\n".join(old_without_minus)