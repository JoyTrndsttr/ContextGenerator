from time import sleep
import json
# from openai import OpenAI
from evaluation import myeval
from utils.RequestModel import OpenAIUtils
from utils.RequestLLMByApi import RequestLLMByApi
from utils.RequestLLM import RequestLLM
import re
import logging

model = OpenAIUtils(model_id="llama:7b")
logging.basicConfig(filename='log.txt', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')
deepseek_model = RequestLLM()
request_llm_by_api = RequestLLMByApi()

def request(llm, prompt, system_prompt=None):
    new_code = ""
    if llm == "deepseek":
        new_code, think, answer = deepseek_model.request_deepseek(prompt, system_prompt)
    elif llm == "deepseek_r1":
        answer = request_llm_by_api.get_deepseek_response(prompt, system_prompt)
    elif llm == "llama":
        new_code, answer = get_model_response(prompt, system_prompt)
    elif llm == "gpt-4o":
        answer = request_llm_by_api.get_gpt_4o_response(prompt, system_prompt)
    else:
        raise ValueError("Invalid llm")
    return new_code, answer

def prompt_for_dataset_valid_or_discard_estimation(old_code: str, review: str, new_code: str) -> str:
    prompt = "\nTask Prompt: Classify Code Review Data Sample for Dataset Quality Filtering"

    prompt += "\nYou are a researcher building a high-quality dataset to train automated code review tools."
    prompt += "\nEach data sample contains:"
    prompt += "\n- A code block (before revision),"
    prompt += "\n- A reviewer’s comment,"
    prompt += "\n- And a revised version of the code block (ground truth)."

    prompt += "\nYour goal is to **categorize this sample** into one of the following types for dataset construction:"

    prompt += "\n\n1. **Valid** —  The developer's change from the code block to the revised version directly reflects or fulfills the intent expressed in the reviewer’s comment."
    prompt += "\n2. **Unclear comment** — The comment is too vague or ambiguous; even a human cannot understand what should be implemented."
    prompt += "\n3. **No change asked** — The comment does not suggest or request any code change."
    prompt += "\n4. **Ignored comment** — The comment does request a code change, but the developer made unrelated changes instead."
    prompt += "\n5. **Wrong linking** — The comment appears to be mistakenly associated with this code block (not semantically relevant)."
    prompt += "\n6. **Other** — Any other invalid case not captured above."

    prompt += "\n\nTo classify correctly:"
    prompt += "\n- First compare the `old_code` and `new_code` to see what changed."
    prompt += "\n- Then analyze whether the change addresses something that was asked or implied by the reviewer’s comment."
    prompt += "\n- **Additionally, generate a new review comment that can perfectly match the code changes between `old_code` and `new_code`.** This new review should reflect the developer's change and fulfill the intent of the reviewer's comment."

    prompt += "\n\nHere is the original code block:"
    prompt += f"\n```\n{old_code}\n```"
    prompt += "\nHere is the reviewer’s comment:"
    prompt += f"\n```\n{review}\n```"
    prompt += "\nHere is the revised code (ground truth):"
    prompt += f"\n```\n{new_code}\n```"

    prompt += "\n\nOutput Format:"
    prompt += "\n```json"
    prompt += "\n{"
    prompt += "\n  \"Classification\": \"<One of: Valid | Unclear comment | No change asked | Ignored comment | Wrong linking | Other>\","
    prompt += "\n  \"Reason\": \"<Brief explanation of your decision>\""
    prompt += "\n  \"New Review\": \"<A modified review that perfectly matches the code changes>\""
    prompt += "\n}"
    prompt += "\n```"

    return prompt

def prompt_for_repo_context_dependency_estimation(old_code: str, review: str, new_code: str, review_info) -> str:
    prompt = "\nTask Prompt: Evaluate Whether a Code Refinement Task Requires Repository Context"

    prompt += "\nYou are a researcher studying code refinement models. You are analyzing a dataset where each example consists of:"
    prompt += "\n- A code block (diff hunk);"
    prompt += "\n- A reviewer’s comment (from a pull request);"
    prompt += "\n- A ground truth revision (i.e., how the code block should be modified)."

    prompt += "\nIn this setup, the refinement is done by an automated tool that can only see the code block and the review comment — it does NOT have access to the full codebase."
    prompt += "\nHowever, the tool is allowed to query an Agent that **can** access the repository to retrieve helpful context before modifying the code."

    prompt += "\nThere are two types of context the Agent can query:"
    prompt += "\n- **In-file context**: other parts of the same file as the code block (e.g., checking if there is a helper function *outside* the current code block that could be used to improve or replace code in this block)."
    prompt += "\n- **Cross-file context**: elements defined in other files (e.g., functions, classes, variables, modules)."

    prompt += "\nThe refinement is only considered successful if the tool, without seeing the ground truth, can transform the code block to exactly match the ground truth."

    prompt += "\nYour task is to determine whether this refinement task **requires** repository-level context (via the Agent) in order to succeed."

    prompt += "\n\nTo make this decision, follow these steps:"

    prompt += "\n1. **Compare the original code block and the ground truth**:"
    prompt += "\n   - If the change is modifications of document/comment or name/format convention, etc., context is likely not needed."
    prompt += "\n   - If the change involves modifications or additions about bugs/new features, etc., context may be needed."

    prompt += "\n2. **Analyze the reviewer’s comment and its relevance to the change**:"
    prompt += "\n   - Focus on what concrete change is being suggested in the comment, not whether a change is necessary."
    prompt += "\n   - For example, if the review discusses whether it is necessary to delete or refactor a specific piece of code, your responsibility is to focus only on *how* to perform the operation if it were to be done."
    prompt += "\n   - If the review inspired the key additions or modifications in the ground truth, then it likely guided the refinement."
    prompt += "\n   - If the review does not relate to the observed changes at all, then context is likely not needed for this sample."

    prompt += "\n3. **Identify new elements introduced in the change**:"
    prompt += "\n   - Focus on added lines (`+`) in the ground truth. Extract any newly elements that have never appeared in the original code block or the review comment."
    prompt += "\n   - If the new element appears **explicitly** in the review comment (even if not present in the original code block), it does **not** count as requiring additional context."
    prompt += "\n   - If the new element appears in neither the code block nor the review comment, but is clearly inferred from an existing element's name or usage (e.g., calling a function likely related to an identifier in the original block), then context is **more likely** required."
    prompt += "\n   - Exclude Python built-in names and natural language content(e.g., comments, docstrings) from consideration."

    prompt += "\n\nHere is the code block under review:"
    prompt += f"\n```\n{old_code}\n```"
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else: prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review
    prompt += "\nHere is the ground truth revision:"
    prompt += f"\n```\n{new_code}\n```"

    prompt += "\n\nOutput Format (in JSON):"
    prompt += "\n```json"
    prompt += "\n{"
    prompt += "\n  \"Additional_context_required\": 0 or 1,"
    prompt += "\n  \"Reason_for_require_additional_context\": \"<Brief explanation of why context is or isn’t needed, referencing specific aspects of the change and comment.>\""
    prompt += "\n}"
    prompt += "\n```"

    return prompt

def prompt_for_additional_context_required(old: str, review: str, review_info) -> str:
    prompt = "\nTask Prompt: Decide Whether You, an Automated Code Review Tool, Need Additional Context to Refine a Problematic Code Block"

    prompt += "\nYou are an automated code review tool. You have received the following reviewer comment:"
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else: prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review

    prompt += "\nThe comment refers to the following code block (diff hunk):"
    prompt += f"\n```\n{old}\n```"

    prompt += "\nYour job is to refine this code based on the reviewer’s intent and the code block alone."

    prompt += "\nHowever, unlike a human developer, you do **not** have direct access to the rest of the source code repository."

    prompt += "\nWhen necessary, you may ask questions to an **Agent** that is capable of accessing the full repository and retrieving helpful context for you."

    prompt += "\nYou should only ask the Agent for help if you believe that resolving your uncertainty will significantly affect your ability to make a correct code change."

    prompt += "\nThere are two types of context you may ask about:"
    prompt += "\n- **In-file context**: Information from other parts of the *same file* as the code block. For example, the file might define a helper function *outside* the current code block that could be used to improve or replace code in this block."
    prompt += "\n- **Cross-file context**: Information defined in *other files* of the repository, such as how a function, variable, class, or module is implemented."

    prompt += "\nYour analysis should focus on:"
    prompt += "\n- **What specific change is being suggested** in the reviewer’s comment — not whether that change is necessary."
    prompt += "\n  For example, even if the comment questions whether it’s worth deleting or refactoring a piece of code, you should assume the change will be made and focus on *how* to implement it."
    prompt += "\n- **Whether the changes in this code block align with the reviewer’s intent** — you do not need to consider how it affects the rest of the codebase."
    prompt += "\n  For example, if the comment suggests renaming an element, you don’t need to check for downstream breakage — those will be handled in future commits."
    
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

def prompt_for_in_file_context_summary(review: str, source_code: str, question: str, review_info) -> str:
    prompt = "\nTask Prompt: You Are an Agent Summarizing In-File Context to Support Automated Code Refinement"

    prompt += "\nYou are an intelligent Agent that assists an automated code review tool."
    prompt += "\nThe tool received the following review comment as guidance for how to improve a code block:"
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else: prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review

    prompt += "\nThe tool is attempting to modify the code block accordingly, but it does not have access to the full file."
    prompt += "\nIt has asked you to answer the following question, which it generated in order to better understand the context needed for this change:"
    prompt += f"\n```\n{question}\n```"

    prompt += "\nYou do have access to the **entire source file** that contains the code block in question. The contents of the file are:"
    prompt += f"\n```\n{source_code}\n```"

    prompt += "\nYour analysis should focus on:"
    prompt += "\n- **What specific change is being suggested** in the reviewer’s comment — not whether that change is necessary."
    prompt += "\n  For example, even if the comment questions whether it’s worth deleting or refactoring a piece of code, you should assume the change will be made and focus on *how* to implement it."
    prompt += "\n- **Whether the changes in this code block align with the reviewer’s intent** — you do not need to consider how it affects the rest of the codebase."
    prompt += "\n  For example, if the comment suggests renaming an element, you don’t need to check for downstream breakage — those will be handled in future commits."

    prompt += "\n\nYour task:"
    prompt += "\n- Analyze the full file to locate any information relevant to answering the tool’s question."
    prompt += "\n- Focus on parts of the file that help clarify or support what change is being suggested in the review."
    prompt += "\n- Your summary should only include information that helps the tool decide *how* to modify the current code block correctly based on file-level context."

    prompt += "\n\nOutput Format:"
    prompt += "\n- Provide a clear and concise summary (less than 100 words) that directly addresses the tool’s question."
    prompt += "\n- Format your output as a JSON object:"
    prompt += "\n```json"
    prompt += "\n{\"Summary\": \"<your summary here>\"}"
    prompt += "\n```"

    return prompt

def prompt_for_in_file_context_summary_without_question(original_code: str, review: str, source_code: str, review_info) -> str:
    prompt = "\nTask Prompt: You Are an Agent Summarizing In-File Context to Support Automated Code Refinement"

    prompt += "\nYou are an intelligent Agent that assists an automated code review tool."

    prompt += "\nThe tool received the following code block to refine:"
    prompt += f"\n```\n{original_code}\n```"

    prompt += "\nThe tool also received the following reviewer comment as guidance for how to improve that code:"
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else:
            prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review

    prompt += "\nThe tool does not have access to the full file containing this code, so it has asked you to summarize any relevant context from that file."

    prompt += "\nYou have access to the **entire source file** that contains the code block. The contents of the file are:"
    prompt += f"\n```\n{source_code}\n```"

    prompt += "\n\nYour task:"
    prompt += "\n- Analyze the full file to locate any information that may help clarify or support what change is being suggested in the review comment."
    prompt += "\n- Focus on parts of the file that help the tool determine *how* to modify the current code block correctly based on the reviewer’s intent."

    prompt += "\n\nYour analysis should focus on:"
    prompt += "\n- **What specific change is being suggested** in the reviewer’s comment — not whether that change is necessary."
    prompt += "\n  For example, even if the comment questions whether it’s worth deleting or refactoring a piece of code, you should assume the change will be made and focus on *how* to implement it."
    prompt += "\n- **Whether the changes in this code block align with the reviewer’s intent** — you do not need to consider how it affects the rest of the codebase."

    prompt += "\n\nOutput Format:"
    prompt += "\n- Provide a clear and concise summary (less than 100 words) of the relevant file-level context."
    prompt += "\n- Format your output as a JSON object:"
    prompt += "\n```json"
    prompt += "\n{\"Summary\": \"<your summary here>\"}"
    prompt += "\n```"

    return prompt

def prompt_for_refinement(old_without_minus, review, review_info, question_for_in_file_context, in_file_context_summary, question_for_cross_file_context, cross_file_context_summary):
    prompt = ""
    prompt += "As a developer, imagine you've submitted a pull request and" \
              " your team leader requests you to make a change to a piece of code." \
              " The old code being referred to in the hunk of code changes is:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else: prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review

    # if question_for_in_file_context or question_for_cross_file_context:
    #     prompt += "\n\nBased on the review, you still have some specific questions:"
    #     if question_for_in_file_context:
    #         prompt += f"\n- You asked an Agent to check the file containing this code block to answer the following question:"
    #         prompt += f"\n{question_for_in_file_context}"
    #         prompt += f"\nThe Agent checked the file and provided the following summary:"
    #         prompt += f"\n{in_file_context_summary}"
    #     if question_for_cross_file_context:
    #         prompt += f"\n- You also asked the Agent to check some cross-file definitions to answer the following question:"
    #         prompt += f"\n{question_for_cross_file_context}"
    #         prompt += f"\nThe Agent checked these elements and provided the following summary:"
    #         prompt += f"\n{cross_file_context_summary}"
    #     prompt += "\n\nYour Task:"
    
    if question_for_in_file_context or question_for_cross_file_context:
        prompt += "\n\nBased on the review, you check the source code and find that:"
        if question_for_in_file_context:
            prompt += f"\n{in_file_context_summary}"
        if question_for_cross_file_context:
            prompt += f"\n{cross_file_context_summary}"
        prompt += "\n\nYour Task:"

    prompt += "\nPlease generate the revised code according to the review. " \
              "Please ensure that the revised code follows the original code format" \
              " and comments, unless it is explicitly required by the review."
    return prompt

def prompt_for_cross_file_context_request(old_without_minus: str, review: str, question: str, calls: list, name_list: list, review_info) -> str:
    prompt = "\nTask Prompt: Decide Whether to Ask an Agent for Cross-File Context to Support Automated Code Refinement"

    prompt += "\nYou are an automated code review tool. You have been asked to refine a code block based on the following reviewer comment:"
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else: prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review

    prompt += "\nThe relevant code block (diff hunk) you are working on is:"
    prompt += f"\n```\n{old_without_minus}\n```"

    prompt += "\nThrough your previous analysis of the code block and review comment, you have determined that:"
    prompt += "\n- **Cross-file context** may be required — specifically, information defined in *other files* of the repository, such as how a function, variable, class, or module is implemented."

    prompt += f"\nAs a result, you have formulated the following question for the Agent:\n```\n{question}\n```"

    prompt += "\nYou cannot see the rest of the repository directly. However, when needed, you may ask an **Agent** to retrieve the definition and implementation of one specific element at a time — such as a function, class, variable, or module — from the full repository."

    prompt += "\nYou should only ask about an element if:"
    prompt += "\n- It is likely project-specific (not a Python built-in), and"
    prompt += "\n- It appears in the code block, the review comment, or can be reasonably inferred as relevant to the modification task."

    prompt += "\nDo not re-ask about any elements that have already been retrieved earlier."

    if len(calls) > 0:
        if len(name_list) > 0:
            prompt += "\n\nRepository Context Retrieved So Far:"
            prompt += f"\nYou have already asked about: {', '.join(name_list)}"

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
    prompt += "\n- Do you still need to ask the Agent for additional cross-file context?"
    prompt += "\n- If yes, which element (function/class/etc.) do you want to retrieve next?"
    prompt += "\n- What is the exact question or issue you hope to resolve by checking that element?"

    prompt += "\nYour analysis should focus on:"
    prompt += "\n- **What specific change is being suggested** in the reviewer’s comment — not whether that change is necessary."
    prompt += "\n  For example, even if the comment questions whether it’s worth deleting or refactoring a piece of code, you should assume the change will be made and focus on *how* to implement it."
    prompt += "\n- **Whether the changes in this code block align with the reviewer’s intent** — you do not need to consider how it affects the rest of the codebase."
    prompt += "\n  For example, if the comment suggests renaming an element, you don’t need to check for downstream breakage — those will be handled in future commits."

    prompt += "\n\nOnly ask if it is likely to significantly improve the correctness of your code change."
    prompt += "\n\nOutput Format (in JSON):"
    prompt += "\n```json"
    prompt += "\n{"
    prompt += "\n  \"Additional_context_required\": 0 or 1,"
    prompt += "\n  \"Element_name_to_retrieve\": \"<Name of the function, class, or variable you want to inspect>\","
    prompt += "\n  \"Question_for_element\": \"In no more than 50 words, describe what specific issue or question you hope to resolve by looking at this element’s definition and implementation.\""
    prompt += "\n}"
    prompt += "\n```"

    return prompt

def prompt_for_cross_file_context_summary(review: str, question: str, calls: list, review_info) -> str:
    prompt = "\nTask Prompt: Summarize Cross-File Context to Help an Automated Tool Refine Code Based on Its Question"

    prompt += "\nYou are an intelligent Agent assisting an automated code review tool with code refinement."

    prompt += "\nThe tool received the following reviewer comment as input:"
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else: prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review

    prompt += "\nThe tool is refining a specific code block based on this review, but it does **not** have access to the full code repository."

    prompt += "\nTo resolve a potential ambiguity, the tool has generated the following question and asked you to retrieve and summarize relevant cross-file context:"
    prompt += f"\n```\n{question}\n```"

    prompt += "\nYou have searched the repository and gathered the relevant definitions or usages of certain functions, classes, or variables that may help answer the question."

    if len(calls) > 0:
        prompt += "\n\nHere is the repository context you found:"
        for i, call in enumerate(calls, start=1):
            caller, callee, callee_text, callee_context, callee_purpose = call
            if caller == callee or caller == "default_function":
                prompt += f"\nCallee {i}: `{callee}`"
            else:
                prompt += f"\nCall {i}: `{caller}` calls `{callee}`"
            callee_text_lines = callee_text.split('\n')
            if len(callee_text_lines) > 100: callee_text = "\n".join(callee_text_lines[:100]) + "\n #The rest of the definition is too long to display."
            prompt += f"\nCallee Implementation:\n```\n{callee_text}\n```"
            # prompt += f"\nPurpose for Checking This Callee: {callee_purpose}"

    prompt += "\n\nYour task:"
    prompt += "\nBased on your findings and the tool’s question, provide a concise summary of the most relevant information needed to answer that question."
    prompt += "\nAvoid generic descriptions — include only information that is necessary for resolving the issue raised in the question."
    
    prompt += "\nYour analysis should focus on:"
    prompt += "\n- **What specific change is being suggested** in the reviewer’s comment — not whether that change is necessary."
    prompt += "\n  For example, even if the comment questions whether it’s worth deleting or refactoring a piece of code, you should assume the change will be made and focus on *how* to implement it."
    prompt += "\n- **Whether the changes in this code block align with the reviewer’s intent** — you do not need to consider how it affects the rest of the codebase."
    prompt += "\n  For example, if the comment suggests renaming an element, you don’t need to check for downstream breakage — those will be handled in future commits."

    prompt += "\n\nOutput Requirements:"
    prompt += "\n- Your summary should be under 100 words."
    prompt += "\n- Make it concise, factual, and focused on helping the tool make an accurate code change."
    prompt += "\n- Format your response as a JSON object like this:"
    prompt += "\n```json"
    prompt += "\n{\"Summary\": \"<your summary here>\"}"
    prompt += "\n```"

    return prompt

def prompt_for_cross_file_context_summary_without_question(original_code: str, review: str, definitions: list, review_info) -> str:
    prompt = "\nTask Prompt: Summarize Cross-File Context to Help an Automated Tool Refine Code"

    prompt += "\nYou are an intelligent Agent assisting an automated code review tool with code refinement."
    prompt += "\nThe tool received the following code block:"
    prompt += f"\n```\n{original_code}\n```"

    prompt += "\nThe tool received the following reviewer comment as input:"
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else:
            prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review

    prompt += "\nThe tool is refining a specific code block based on this review, but it does **not** have access to the full code repository."

    prompt += "\nYou have access to the full code repository and have retrieved relevant definitions of functions, classes, or variables that may help clarify the intent."

    if len(definitions) > 0:
        prompt += "\n\nHere are the relevant definitions you found:"
        for i, (name, definition_text) in enumerate(definitions):
            prompt += f"\nDefinition {i}: `{name}`"
            definition_text_lines = definition_text.split('\n')
            if len(definition_text_lines) > 100:
                definition_text = "\n".join(definition_text_lines[:100]) + "\n #The rest of the definition is too long to display."
            prompt += f"\nImplementation:\n```\n{definition_text}\n```"

    prompt += "\n\nYour task:"
    prompt += "\nBased on your findings and the reviewer’s comment, provide a concise summary of the most relevant cross-file context information that may assist in refining the code."

    prompt += "\nYour analysis should focus on:"
    prompt += "\n- **What specific change is being suggested** in the reviewer’s comment — not whether that change is necessary."
    prompt += "\n  For example, even if the comment questions whether it’s worth deleting or refactoring a piece of code, you should assume the change will be made and focus on *how* to implement it."
    prompt += "\n- **Whether the changes in this code block align with the reviewer’s intent** — you do not need to consider how it affects the rest of the codebase."

    prompt += "\n\nOutput Requirements:"
    prompt += "\n- Your summary should be under 100 words."
    prompt += "\n- Make it concise, factual, and focused on helping the tool make an accurate code change."
    prompt += "\n- Format your response as a JSON object like this:"
    prompt += "\n```json"
    prompt += "\n{\"Summary\": \"<your summary here>\"}"
    prompt += "\n```"

    return prompt

def prompt_for_evaluating_summary(old_without_minus: str, review: str, question: str, summary: str, review_info) -> str:
    prompt = "\nTask Prompt: Evaluate Whether the Agent’s Summary Has Answered Your Question"

    prompt += "\nYou are an automated code review tool refining a code block based on the following reviewer comment:"
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else: prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review

    prompt += "\nHowever, you can only see the code block and the review comment. You do not have access to the rest of the repository."

    prompt += "\nTo address a knowledge gap, you asked an Agent to retrieve repository context and help answer the following question:"
    prompt += f"\n```\n{question}\n```"

    prompt += "\nHere is the code block you are trying to refine:"
    prompt += f"\n```\n{old_without_minus}\n```"

    prompt += "\nThe Agent reviewed the repository and returned the following summary:"
    prompt += f"\n```json\n{{\"Summary\": \"{summary}\"}}\n```"

    prompt += "\nYour task is to evaluate whether this summary:"
    prompt += "\n- Is helpful for making the correct change,"
    prompt += "\n- And whether it fully resolves your original question."

    prompt += "\nIf the summary directly and clearly answers your question, set:"
    prompt += "\n  - `Question_resolved = 1`"
    prompt += "\n  - `Summary_useful = 1`"

    prompt += "\nIf the summary is helpful but does not fully answer your question, set:"
    prompt += "\n  - `Question_resolved = 0`"
    prompt += "\n  - `Summary_useful = 1`"
    prompt += "\n  - Then rewrite your question in a clearer or more targeted way, based on what the summary clarified."

    prompt += "\nIf the summary is irrelevant or unhelpful, set:"
    prompt += "\n  - `Question_resolved = 0`"
    prompt += "\n  - `Summary_useful = 0`"
    prompt += "\n  - And optionally revise your question to make it more answerable."

    prompt += "\nYour analysis should focus on:"
    prompt += "\n- **What specific change is being suggested** in the reviewer’s comment — not whether that change is necessary."
    prompt += "\n  For example, even if the comment questions whether it’s worth deleting or refactoring a piece of code, you should assume the change will be made and focus on *how* to implement it."
    prompt += "\n- **Whether the changes in this code block align with the reviewer’s intent** — you do not need to consider how it affects the rest of the codebase."
    prompt += "\n  For example, if the comment suggests renaming an element, you don’t need to check for downstream breakage — those will be handled in future commits."

    prompt += "\n\nOutput Format:"
    prompt += "\n```json"
    prompt += "\n{"
    prompt += "\n  \"Question_resolved\": 0 or 1,"
    prompt += "\n  \"Summary_useful\": 0 or 1,"
    prompt += "\n  \"New_question\": \"<If applicable, revise your question here; otherwise, repeat the original question>\""
    prompt += "\n}"
    prompt += "\n```"

    return prompt

def get_model_response(user_prompt, system_prompt = None):
    answer = model.get_completion(user_prompt, system_prompt if system_prompt else None)
    result = re.search(r'```(.*)```', answer,re.DOTALL)
    print(f"prompt:\n{user_prompt}\nanswer:\n{answer}")
    if result:
        newcode = result.group(1)
    return newcode if result else "", answer

def get_deepseek_response(user_prompt, system_prompt = None):
    code, _, answer = deepseek_model.request_deepseek(user_prompt, system_prompt if system_prompt else None)
    return code, answer

def get_full_deepseek_response(user_prompt, system_prompt = None):
    code, think, answer = deepseek_model.request_deepseek(user_prompt, system_prompt if system_prompt else None)
    return code, think, answer

def get_deepseek_r1_response(user_prompt, system_prompt = None):
    answer= request_llm_by_api.get_deepseek_response(user_prompt, system_prompt if system_prompt else None)
    code = re.search(r'```(.*)```', answer,re.DOTALL)
    if code:
        code = code.group(1)
    return code, answer

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

def prompt_for_names_of_relevance_context(review: str, source_code: str, question: str, review_info) -> str:
    prompt = "\nTask Prompt: Identify Relevant Context Names in File to Support Code Refinement"

    prompt += "\nYou are an intelligent Agent assisting an automated code review tool."
    prompt += "\nThe tool received the following review comment as guidance for how to improve a code block:"
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "\nThe code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"\nThe reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':"
        else:
            prompt += f"\nThe reviewer commented on the line '{review_info['review_position_line']}':"
    prompt += f"\n```\n{review}\n```"

    prompt += "\nThe tool is trying to refine the code accordingly, but it does not have access to the rest of the file."
    prompt += "\nTo assist, it has asked the following question to help guide the modification:"
    prompt += f"\n```\n{question}\n```"

    prompt += "\nYou have access to the **entire source file** that contains the relevant code block. The file content is:"
    prompt += f"\n```\n{source_code}\n```"

    prompt += "\n\nYour task:"
    prompt += "\n- Carefully read the full file to identify code elements that are relevant to answering the tool's question."
    prompt += "\n- These elements may include variables, functions, classes, or modules that are directly involved in, mentioned by, or logically required to implement the reviewer’s intended change."
    prompt += "\n- For example, if the comment says a certain method should be used and you find that this method belongs to a specific class, then that class is also likely part of the relevant context."
    prompt += "\n- Similarly, if the comment mentions a method that cannot be found in the file, and you reasonably suspect it belongs to a certain module, then that module name should also be included."
    prompt += "\n- Do NOT include natural language terms (e.g., comments or docstrings). Only include **Python code identifiers**."
    prompt += "\n- If you encounter a compound expression like `val.func1`, split and include both `val` and `func1` separately."
    prompt += "\n- Provide as many as possible, but no more than **10** relevant names."

    prompt += "\n\nAlso provide the purpose of retrieving those context names:"
    prompt += "\nThe goal is to help the tool identify which parts of the file might provide critical information for answering its question — for example:"
    prompt += "\n- To determine whether a certain class contains helper methods relevant to the modification;"
    prompt += "\n- To find out the signature or behavior of a function that may be reused;"
    prompt += "\n- Or to locate the definition of a module or variable that is referenced but not fully visible in the code block."

    prompt += "\n\nOutput Format:"
    prompt += "\nReturn your response in the following JSON format:"
    prompt += "\n```json"
    prompt += "\n{"
    prompt += "\n  \"Candidate Context Names\": [\"name1\", \"name2\", ..., \"nameN\"],"
    prompt += "\n  \"Purpose\": \"<Brief sentence describing why these names are relevant to answering the tool’s question>\""
    prompt += "\n}"
    prompt += "\n```"

    return prompt

def prompt_for_deeper_names_of_relevance_context(review: str, question: str, calls: list, purpose: str) -> str:
    prompt = "\nTask Prompt: Identify Deeper-Level Relevant Context Names from Function/Class Definitions"

    prompt += "\nYou are an intelligent Agent assisting an automated code review tool."
    prompt += "\nThe tool is refining a code block based on the following reviewer comment:"
    prompt += f"\n```\n{review}\n```"

    prompt += "\nIt has also asked the following question to better guide the code modification:"
    prompt += f"\n```\n{question}\n```"

    prompt += "\nPreviously, you examined the source file and identified some related functions or classes."
    prompt += "\nNow you are provided with the actual definitions of those elements, and your job is to read them carefully and identify **deeper-level context names** that may help further answer the tool’s question."

    prompt += "The purpose to retrieve these deeper-level context names is:"
    prompt += f"\n```\n{purpose}\n```"

    if len(calls) > 0:
        prompt += "\n\nHere are the available code definitions you should examine:"
        for i, call in enumerate(calls, start=1):
            caller, callee, callee_text, callee_context, callee_purpose = call
            if caller == callee or caller == "default_function":
                prompt += f"\nCallee {i}: `{callee}`"
            else:
                prompt += f"\nCall {i}: `{caller}` calls `{callee}`"
            callee_text_lines = callee_text.split('\n')
            if len(callee_text_lines) > 100: callee_text = "\n".join(callee_text_lines[:100]) + "\n #The rest of the definition is too long to display."
            prompt += f"\nCallee Implementation:\n```\n{callee_text}\n```"
            # prompt += f"\nPurpose for Checking This Callee: {callee_purpose}"
    
    prompt += "\n\nYour task:"
    prompt += "\n- Carefully read the code definitions provided above."
    prompt += "\n- Identify any new variables, functions, classes, or modules in them that are **likely useful** for answering the question or implementing the reviewed change."
    prompt += "\n- For example, if a helper function defines a call to another method or accesses a utility object, that newly referenced name may be important to retrieve."
    prompt += "\n- Do NOT include natural language elements (e.g., comments, docstrings). Only extract Python identifiers."
    prompt += "\n- If compound calls are observed (e.g., `obj.helper()`), include both `obj` and `helper` as individual names."
    prompt += "\n- Do not list any name that was already surfaced in a previous context collection round."
    prompt += "\n- Provide as many as necessary, but **no more than 10**."

    prompt += "\n\nPurpose of retrieving these deeper-level context names:"
    prompt += "\nThese names will guide the tool in requesting additional context from the repository if needed — such as locating a helper method’s body, checking an object's structure, or validating how a returned value is handled elsewhere."

    prompt += "\n\nOutput Format:"
    prompt += "\n```json"
    prompt += "\n{"
    prompt += "\n  \"Candidate Context Names\": [\"name1\", \"name2\", ..., \"nameN\"],"
    prompt += "\n  \"Purpose\": \"<Brief sentence describing what the tool is trying to figure out by checking these names>\""
    prompt += "\n}"
    prompt += "\n```"

    return prompt

def get_intention_prompt(data):
    system_prompt = "You will be presented with a code review comment and a code snippet. "
    system_prompt += "Your task is to understand the reviewer's intention of the modification without explaining the reason. "
    system_prompt += "Choose one of the following templates to describe the reviewer's intention. "
    system_prompt += "Do not change the original words in the template; "
    system_prompt += "fill in the words in parentheses and fill in the code inside the code block according to the context.\n"
    system_prompt += "Single-line change. Change word (old_word) to (new_word)\n"
    system_prompt += "Single-line change. Delete word (word_to_delete)\n"
    system_prompt += "Single-line change. Change the code to ```new_code```\n"
    system_prompt += "Single-line change. Delete code ```code_to_delete```\n"
    system_prompt += "Multi-line change. Delete code lines ```code_lines_to_delete```\n"
    system_prompt += "Multi-line change. Change the code lines ```old_code_lines``` to ```new_code_lines```\n"
    # print("system_prompt:", system_prompt)
    # input("press enter to continue")

    comment = data["comment"]
    review_line = data["review_line"]
    old_code = data["old_code"]
    prompt = ""
    prompt += "The reviewer gave the following comment:\n"
    prompt += "{}\n".format(comment)
    prompt += "The original code is as follows:\n"
    prompt += "```\n{}\n```\n".format(old_code)
    prompt += "The review comment is related to the following code line:\n"
    prompt += "{}\n".format(review_line)
    # reviewer's intention 是什么
    prompt += "What is the reviewer's intention of the modification?\n"
    return system_prompt, prompt

def get_selfgen_prompt(data):
    intention = data["intention"]
    old_code = data["old_code"]
    review_line = data["review_line"]
    prompt = ""
    prompt += "During a code review, the reviewer asked the developer to revise this piece of code, the original code is as follows:\n"
    prompt += "```\n{}\n```\n".format(old_code)
    prompt += "The review comment is related to the following code line:\n"
    prompt += "{}\n".format(review_line)
    prompt += "The reviewer's intention is:\n{}\n".format(intention)
    prompt += "Revise the original code according to the reviewer's intention.\n"
    prompt += "# Instruction:\n"
    prompt += "## Recall relevant exemplars:\n"
    # 提供三个code review的例子。根据<Origianl Code>, <Review Intention>, <Intention Related Line>，分析得到<Revised Code>
    prompt += "  provide three code review examples. According to <Origianl Code>, <Review Intention> and <Intention Related Line> analyze and get <Revised Code>.\n"
    prompt += "## Solve the initial problem:\n"
    # 先复述一下initial problem，然后根据例子，分析得到<Revised Code>
    prompt += "  Repeat the initial problem, then analyze and get <Revised Code> according to the examples.\n"
    # 一步一步的解决问题
    prompt += "Please solve the problem step by step.\n"
    return prompt

def simple_prompt(comment, old_code, review_line):
    prompt = "During a code review, the reviewer asked the developer to revise this piece of code, the original code is as follows:\n"
    prompt += "```\n{}```\n".format(old_code)
    prompt += "The reviewer gave the following comment:\n"
    prompt += "{}\n".format(comment)
    prompt += "The review comment is related to the following code line:\n"
    prompt += "{}\n".format(review_line)
    prompt += "Revise the original code according to the review comment.\n"
    return prompt

def simple_prompt_with_in_file_context(comment, old_code, review_line, in_file_context):
    prompt = "During a code review, the reviewer asked the developer to revise this piece of code, the original code is as follows:\n"
    prompt += "```\n{}```\n".format(old_code)
    prompt += "The reviewer gave the following comment:\n"
    prompt += "{}\n".format(comment)
    prompt += "The review comment is related to the following code line:\n"
    prompt += "{}\n".format(review_line)
    prompt += "Revise the original code according to the review comment.\n"
    return prompt

def simple_prompt_with_cross_file_context(comment, old_code, review_line, cross_file_context):
    prompt = "During a code review, the reviewer asked the developer to revise this piece of code, the original code is as follows:\n"
    prompt += "```\n{}```\n".format(old_code)
    prompt += "The reviewer gave the following comment:\n"
    prompt += "{}\n".format(comment)
    prompt += "The review comment is related to the following code line:\n"
    prompt += "{}\n".format(review_line)
    prompt += "Revise the original code according to the review comment.\n"
    return prompt

def simple_prompt_with_rag(comment, old_code, review_line, example_datas):
    # 这是一些code review的例子，请参考这些例子，然后完成code review
    prompt = "Here are some examples of code reviews, please refer to these examples and then complete the code review.\n"
    for example_data in example_datas:
        example_comment = example_data["comment"]
        example_old_code = example_data["old_code"]
        example_review_line = example_data["review_line"]
        example_new_code = example_data["new_code"]
        prompt += "<Origianl Code>:\n```\n{}\n```\n".format(example_old_code)
        prompt += "<Review Comment>:\n{}\n".format(example_comment)
        prompt += "<Comment Related Line>:\n{}\n".format(example_review_line)
        prompt += "<Revised Code>:\n```\n{}\n```\n".format(example_new_code)
    prompt += "During a code review, the reviewer asked the developer to revise this piece of code, the original code is as follows:\n"
    prompt += "```\n{}\n```\n".format(old_code)
    prompt += "The reviewer gave the following comment:\n"
    prompt += "{}\n".format(comment)
    prompt += "The review comment is related to the following code line:\n"
    prompt += "{}\n".format(review_line)
    prompt += "Revise the original code according to the review comment.\n"
    prompt += "Let's think step by step.\n"
    return prompt

def simple_prompt_with_in_file_context(comment, old_code, review_line, in_file_context):
    prompt = "During a code review, the reviewer asked the developer to revise this piece of code, the original code is as follows:\n"
    prompt += "```\n{}```\n".format(old_code)
    prompt += "The reviewer gave the following comment:\n"
    prompt += "{}\n".format(comment)
    prompt += "The review comment is related to the following code line:\n"
    prompt += "{}\n".format(review_line)
    prompt += "\n\nBased on the review, you check the source code and find that:"
    prompt += f"\n{in_file_context}"
    prompt += "Revise the original code according to the review comment.\n"
    return prompt

def simple_prompt_with_cross_file_context(comment, old_code, review_line, in_file_context, cross_file_context):
    prompt = "During a code review, the reviewer asked the developer to revise this piece of code, the original code is as follows:\n"
    prompt += "```\n{}```\n".format(old_code)
    prompt += "The reviewer gave the following comment:\n"
    prompt += "{}\n".format(comment)
    prompt += "The review comment is related to the following code line:\n"
    prompt += "{}\n".format(review_line)
    prompt += "\n\nBased on the review, you check the source code and find that:"
    prompt += f"\n{in_file_context}"
    prompt += f"\n{cross_file_context}"
    prompt += "Revise the original code according to the review comment.\n"
    return prompt
