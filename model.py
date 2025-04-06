# 数据库连接配置
from time import sleep
import json
from openai import OpenAI
from evaluation import myeval
from utils.RequestModel import OpenAIUtils
from utils.RequestLLM import RequestLLM
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
deepseek_model = RequestLLM()

def prompt_for_repo_context_dependency_estimation(old_code: str, review: str, new_code: str) -> str:
    prompt = "\nTask Prompt: Evaluate Whether a Code Refinement Task Requires Repository Context to Succeed"

    prompt += "\nYou are a researcher studying code refinement models. You are analyzing a dataset where each example consists of:"
    prompt += "\n- A code block (diff hunk);"
    prompt += "\n- A reviewer’s comment (from a pull request);"
    prompt += "\n- A ground truth revision (i.e., how the code block should be modified)."

    prompt += "\nIn this setup, the refinement is done by an automated tool that can only see the code block and the review comment — it does NOT have access to the full codebase."
    prompt += "\nHowever, the tool is allowed to query an Agent that **can** access the repository to retrieve helpful context before modifying the code."

    prompt += "\nThere are two types of context the Agent can query:"
    prompt += "\n- In-file context: other parts of the same file as the code block (e.g., checking if a function is used elsewhere in the file)."
    prompt += "\n- Cross-file context: elements defined in other files (e.g., functions, classes, variables, modules)."

    prompt += "\nThe refinement is only considered successful if the tool, without seeing the ground truth, can transform the code block to exactly match the ground truth."

    prompt += "\nYour task is to determine whether this refinement task **requires** repository-level context (via the Agent) in order to succeed."

    prompt += "\n\nTo make this decision, follow these steps:"

    prompt += "\n1. **Compare the original code block and the ground truth**:"
    prompt += "\n   - If the change is a simple deletion or modify document/comment or name/format convention, etc., context is likely not needed."
    prompt += "\n   - If the change involves modifications or additions about bugs/new features, etc., context may be needed."

    prompt += "\n2. **Analyze the reviewer’s comment**:"
    prompt += "\n   - Focus on what change is being suggested, not whether a change is needed."
    prompt += "\n   - If the review directly provides a suggestion like:"
    prompt += "\n     ```\n{suggestion_revised_code}\n```"
    prompt += "\n     and the ground truth simply applies that suggestion, then no context is needed."

    prompt += "\n3. **Identify new elements introduced in the change**:"
    prompt += "\n   - If the change adds or modifies a function, variable, class, or module name that does NOT appear in the original code block or review comment, and"
    prompt += "\n   - This element is very likely defined elsewhere in the project (not a Python built-in),"
    prompt += "\n   - Then repository context is likely required."

    prompt += "\n4. **Check the relevance of the review comment to the change**:"
    prompt += "\n   - If the review has no meaningful influence on the ground truth change, context is not required."
    prompt += "\n   - If the review leads to a change that introduces external elements, context may be required."
    
    prompt += "\nHere is the code block under review:"
    prompt += f"\n```\n{old_code}\n```"
    prompt += f"\nAnd the review is {review}: "
    prompt += "\nHere is the ground truth:"
    prompt += f"\n```\n{new_code}\n```"

    prompt += "\n\nOutput Format (in JSON):"
    prompt += "\n```json"
    prompt += "\n{"
    prompt += "\n  \"Additional_context_required\": 0 or 1,"
    prompt += "\n  \"Reason_for_require_additional_context\": \"<Brief explanation of why context is or isn’t needed, referencing specific aspects of the change and comment.>\""
    prompt += "\n}"
    prompt += "\n```"

    return prompt


def prompt_for_additional_context_required(old: str, review: str) -> str:
    prompt = "\nTask Prompt: Decide Whether You Need Additional Context to Refine a Problematic Code Block You Previously Commented On"

    prompt += "\nYou are a code reviewer who previously left the following comment on a pull request:"
    prompt += f"\n```\n{review}\n```"
    prompt += "\nThe code block that prompted your comment is:"
    prompt += f"\n```\n{old}\n```"

    prompt += "\nNow, because your teammate is busy, you want to refine the code yourself."
    prompt += "\nHowever, you can only see this specific code block (diff hunk) and do NOT have access to other parts of the codebase."
    prompt += "\nYou may consider asking your teammate to look up some information for you—but only if it is highly helpful for making a correct change."
    
    prompt += "\nThere are two types of questions you can ask:"
    prompt += "\n- In-file context: You want to check other parts of the *same file* that might affect how you change the current code. For example, you want to delete a function, but you are unsure if it’s called elsewhere in this file."
    prompt += "\n- Cross-file context: You need to know how a function/variable/class/module is defined or implemented, but suspect it’s defined in another file (due to modularization)."

    prompt += "\nOnly ask for this context if it is important for making a correct change, and you should focus on what change is being suggested in the review, not whether a change is needed."

    prompt += "\n\nOutput Format (in JSON):"
    prompt += "\n```json"
    prompt += "\n{"
    prompt += "\n  \"In_file_context_required\": 0 or 1,"
    prompt += "\n  \"Your_question_for_in_file_context\": \"In no more than 50 words, describe what specific issue or question needs to be resolved by checking other parts of the same file.\","
    prompt += "\n  \"Cross_file_context_required\": 0 or 1,"
    prompt += "\n  \"Your_question_for_cross_file_context\": \"In no more than 50 words, describe what specific issue or question needs to be resolved by checking other files in the repository.\""
    prompt += "\n}"
    prompt += "\n```"

    return prompt

def prompt_for_in_file_context_summary(review: str, source_code: str, question: str) -> str:
    prompt = "\nTask Prompt: Summarize In-File Context to Help a Reviewer Resolve Their Question"

    prompt += "\nYou are assisting a teammate (the reviewer) who is refining a pull request."
    prompt += "\nThey wrote the following code review comment:"
    prompt += f"\n```\n{review}\n```"

    prompt += "\nThey are trying to make a specific change, but need additional information from the rest of the file where the code block appears."

    prompt += f"\nThey've asked the following question:\n```\n{question}\n```"

    prompt += "\nYou have access to the **entire file** that contains the relevant code block. Its contents are shown below:"
    prompt += f"\n```\n{source_code}\n```"

    prompt += "\n\nYour task:"
    prompt += "\n- Carefully read through the file and locate any information that helps answer the question."
    prompt += "\n- Focus on providing only the parts of the file that are directly relevant to the question."
    prompt += "\n- And you should focus on what change is being suggested in the review, not whether a change is needed."

    prompt += "\n\nOutput Format:"
    prompt += "\n- Your response should be under 100 words."
    prompt += "\n- Be clear, specific, and directly address the question."
    prompt += "\n- Format your output as a JSON object like this:"
    prompt += "\n```json"
    prompt += "\n{\"Summary\": \"<your summary here>\"}"
    prompt += "\n```"

    return prompt

def prompt_for_refinement(old_without_minus, review, calls, review_info, with_summary_or_code, with_presice_review_position, clipped_flag, in_file_context_summary, cross_file_context_summary):
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
    if with_summary_or_code == 'summary':
        if in_file_context_summary or cross_file_context_summary: prompt += "\nBased on the review:"
        if in_file_context_summary: prompt += f"\nyou checked the file where the old code is located and find that:{in_file_context_summary}"
        if cross_file_context_summary: prompt += f"\nyou checked some definitions of the elements used in the code block and find that:{cross_file_context_summary}"
    elif with_summary_or_code == 'code':
        #TODO:加入in-file context
        if len(calls) > 0:
            prompt += "\nBased on the review, you checked the repository and find that :\n"
            for call in calls:
                caller, callee, callee_text, callee_context, callee_purpose = call
                callee_text_list = callee_text.split('\n')
                if len(callee_text_list) > 20:
                    concise_callee_text = '\n'.join(callee_text_list[:20])
                match = re.match(r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)\s*:.*$', callee_text_list[0])
                signature = f"{match.group(1)}({match.group(2)})" if match else callee
                main_purpose = callee_context.split('Summary:')
                main_purpose = main_purpose[1].strip() if len(main_purpose) > 1 else callee_context
                if caller == callee or caller == "default_function": 
                    if len(callee_text_list) > 20:
                        prompt += f"\nThe first 20 lines of {signature} are implemented as follows:\n```\n{concise_callee_text}\n``` "
                    else:
                        prompt += f"\n{signature} is defined as:\n```\n{callee_text}\n```"
                else :
                    if len(callee_text_list) > 20:
                        prompt += f"\n{caller} calls {signature}, and the first 20 lines of {signature} are implemented as follows:\n```\n{concise_callee_text}\n``` "
                    else:
                        prompt += f"\n{caller} calls {signature} which is defined as:\n```\n{callee_text}\n```"
    prompt += "\nPlease generate the revised code according to the review. " \
              "Please ensure that the revised code follows the original code format" \
              " and comments, unless it is explicitly required by the review."
    if clipped_flag:
        line_start = old_without_minus.split("\n")[0]
        if line_start.strip() == "": line_start = old_without_minus.split("\n")[1]
        line_end = old_without_minus.split("\n")[-1]
        prompt += f"Specifically,if not required by the review, your code should start with:\"{line_start}\" and end with:\"{line_end}\""
    return prompt

def prompt_for_cross_file_context_request(old_without_minus: str, review: str, question: str, calls: list, name_list: list) -> str:
    prompt = "\nTask Prompt: Decide Whether You Need to Ask for Additional Context to Help Refine the Code"

    prompt += "\nYou are a code reviewer who previously left the following comment on a pull request:"
    prompt += f"\n```\n{review}\n```"
    prompt += "\nThe code block that prompted your comment is:"
    prompt += f"\n```\n{old_without_minus}\n```"

    prompt += f"\nYour overall refinement goal is:\n```\n{question}\n```"

    prompt += "\nYou are now trying to revise the code yourself, but can only see this code hunk. You suspect that some definitions in the project are important to help you implement the correct fix."

    prompt += "\nYou may ask your teammate to help you check the definition and implementation of a specific **function / class / variable / module**, but only one at a time. You should ask *only* if you believe that element is project-specific (not a Python built-in) and clearly appears in:"
    prompt += "\n- your comment,"
    prompt += "\n- or the code block,"
    prompt += "\n- or is otherwise reasonably inferred."

    prompt += "\nAlso, do NOT ask again about elements that you’ve already inquired about earlier."

    if len(calls) > 0:
        if len(name_list) > 0:
            name_str = "Notify the following elements have been asked to retrieve:"
            for name in name_list:
                name_str += f"{name}, "
                prompt += f"\n{name_str[:-2]}"
        for call in calls:
            caller, callee, callee_text, callee_context, callee_purpose = call
            callee_text_list = callee_text.split('\n')
            if len(callee_text_list) > 40:
                concise_callee_text = callee_text_list[0] + "\n"
                for line in callee_text_list[1:]:
                    if "def" in line:
                        concise_callee_text += line + "\n"
            else:
                concise_callee_text = callee_text

            if caller == callee or caller == "default_function":
                if len(callee_text_list) > 40:
                    prompt += f"\nThe concise definition of `{callee}` is:\n```\n{concise_callee_text}\n```"
                else:
                    prompt += f"\n`{callee}` is defined as:\n```\n{callee_text}\n```"
            else:
                if len(callee_text_list) > 40:
                    prompt += f"\n`{caller}` calls `{callee}`, and the concise definition of `{callee}` is:\n```\n{concise_callee_text}\n```"
                else:
                    prompt += f"\n`{caller}` calls `{callee}`, which is defined as:\n```\n{callee_text}\n```"

    prompt += "\n\nNow decide:"
    prompt += "\n- Do you still need to ask for additional cross-file context?"
    prompt += "\n- If yes, which element (function/class/etc.) do you want to retrieve?"
    prompt += "\n- What is the exact question or issue you're trying to resolve by checking that element?"

    prompt += "\n\nOnly ask if it is highly likely to help you refine the code more accurately. If you believe no further questions are needed, just set `Additional_context_required` to 0."
    prompt += "\n- And you should focus on what change is being suggested in the review, not whether a change is needed."

    prompt += "\n\nOutput Format (in JSON):"
    prompt += "\n```json"
    prompt += "\n{"
    prompt += "\n  \"Additional_context_required\": 0 or 1,"
    prompt += "\n  \"Element_name_to_retrieve\": \"<Name of the function, class, or variable you want to inspect>\","
    prompt += "\n  \"Question_for_element\": \"In no more than 50 words, describe what specific issue or question you hope to resolve by looking at this element’s definition and implementation.\""
    prompt += "\n}"
    prompt += "\n```"

    return prompt

def prompt_for_cross_file_context_summary(review: str, question: str, calls: list) -> str:
    prompt = "\nTask Prompt: Summarize Cross-File Context to Help a Teammate Refine Code Based on Their Question"

    prompt += "\nYou are a helpful teammate who has been asked to assist with a code refinement task."
    prompt += "\nYour colleague previously left the following review comment on a pull request:"
    prompt += f"\n```\n{review}\n```"

    prompt += "\nThey are currently refining the code based on that comment, but they cannot access the full repository."
    prompt += "\nThey've asked for your help in looking up some specific cross-file context."
    prompt += f"\nThe specific question they want you to help them answer is:\n```\n{question}\n```"

    prompt += "\nYou have looked up the relevant definitions and implementations of certain functions, classes, or variables from the codebase."

    if len(calls) > 0:
        prompt += "\n\nHere is the repository context you found:"
        for i, call in enumerate(calls, start=1):
            caller, callee, callee_text, callee_context, callee_purpose = call
            if caller == callee or caller == "default_function":
                prompt += f"\nCallee {i}: `{callee}`"
            else:
                prompt += f"\nCall {i}: `{caller}` calls `{callee}`"
            prompt += f"\nCallee Implementation:\n```\n{callee_text}\n```"
            prompt += f"\nPurpose for Checking This Callee: {callee_purpose}"

    prompt += "\n\nYour task:"
    prompt += "\nBased on your findings and your teammate’s question, summarize only the most relevant information needed to answer their question."
    prompt += "\nDo not provide generic descriptions — focus only on what helps answer the specific issue they raised."
    prompt += "\nAnd you should focus on what change is being suggested in the review, not whether a change is needed."

    prompt += "\n\nOutput Requirements:"
    prompt += "\n- Your summary should be under 100 words."
    prompt += "\n- Make it concise, factual, and focused on helping your teammate make an accurate code change."
    prompt += "\n- Format your response as a JSON object like this:"
    prompt += "\n```json"
    prompt += "\n{\"Summary\": \"<your summary here>\"}"
    prompt += "\n```"

    return prompt

def prompt_for_evaluating_summary(old_without_minus: str, review: str, question: str, summary: str) -> str:
    prompt = "\nTask Prompt: Evaluate Whether Your Context Question Has Been Answered by the Provided Summary"

    prompt += "\nYou are the original code reviewer. You previously left this review comment on a pull request:"
    prompt += f"\n```\n{review}\n```"

    prompt += "\nYou are now refining the code yourself. Since you could not access the full codebase, you asked a teammate to look up some repository context for you."

    prompt += f"\nYou asked them the following question:\n```\n{question}\n```"

    prompt += "\nHere is the current version of the code:"
    prompt += f"\n```\n{old_without_minus}\n```"

    prompt += "\nThey summarized what they found as follows:"
    prompt += f"\n```json\n{{\"Summary\": \"{summary}\"}}\n```"

    prompt += "\nYour task is to assess whether their summary was useful and whether it resolved your original question."

    prompt += "\nIf the summary clearly answers your question, set:"
    prompt += "\n  - `Question_resolved = 1`"
    prompt += "\n  - `Summary_useful = 1`"

    prompt += "\nIf the summary is helpful but does not directly resolve your question, set:"
    prompt += "\n  - `Question_resolved = 0`"
    prompt += "\n  - `Summary_useful = 1`"
    prompt += "\n  - and write a revised version of your question in `new_question` that is better aligned with what the summary helps clarify."

    prompt += "\nIf the summary is irrelevant or unhelpful, set:"
    prompt += "\n  - `Question_resolved = 0`"
    prompt += "\n  - `Summary_useful = 0`"
    prompt += "\n  - and revise your question if necessary to make it clearer or more answerable."

    prompt += "\nYou should focus on what change is being suggested in the review, not whether a change is needed."

    prompt += "\n\nOutput Format:"
    prompt += "\n```json"
    prompt += "\n{"
    prompt += "\n  \"Question_resolved\": 0 or 1,"
    prompt += "\n  \"Summary_useful\": 0 or 1,"
    prompt += "\n  \"New_question\": \"<If applicable, revise your question here; otherwise, repeat the original question>\""
    prompt += "\n}"
    prompt += "\n```"

    return prompt

def get_model_response(prompt, temperature=0):
    answer = model.get_completion([prompt])
    result = re.search(r'```(.*)```', answer,re.DOTALL)
    print(f"prompt:\n{prompt}\nanswer:\n{answer}")
    if result: # TODO 由于模型可能会受到提示词的干扰，应该选表现最好的newcode
        newcode = result.group(1)
    return newcode if result else "", answer

def get_deepseek_response(prompt):
    code, _, answer = deepseek_model.request_deepseek(prompt)
    return code, answer

def get_full_deepseek_response(prompt):
    code, think, answer = deepseek_model.request_deepseek(prompt)
    return code, think, answer

def calc_em_and_bleu(new, new_code):
    new_without_plus = remove_prefix(new)
    gpt_em, gpt_em_trim, _, _, gpt_bleu, gpt_bleu_trim \
        = myeval(new_without_plus, new_code)
    return gpt_em, gpt_em_trim, gpt_bleu, gpt_bleu_trim

def remove_prefix(old):
    old_without_minus = [] #去除第一个符号
    for line in old.split("\n"):
        if line.strip() != "":
            old_without_minus.append(line[1:])
    return "\n".join(old_without_minus)