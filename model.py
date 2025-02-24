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
    "temperature": 0.1,
    "top_p": 0.95,
    "n": 1,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0
}

model = OpenAIUtils(model_id="llama:7b", generation_kwargs=generation_kwargs)
logging.basicConfig(filename='log.txt', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

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