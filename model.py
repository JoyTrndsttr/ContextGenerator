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

def prompt_for_repository_context_requirement(old, review, new):
    prompt = "\nTask Prompt for Evaluating Additional Context Requirements in Code Review:"
    prompt += "\nAs an experienced evaluator, your task is to rigorously determine whether additional project-specific context is needed to implement changes suggested in a code review accurately. Focus on identifying distinct code elements such as functions or variables mentioned in the reviewer's comment or observed in the ground truth that are absent from the provided code block."
    prompt += "\nInstructions:"
    prompt += "\nReview the Provided Information:"
    prompt += f"\nReviewer's Comment: \n```\n{review}\n```"
    prompt += f"\nAssociated Code Block: \n```\n{old}\n```"
    prompt += f"\nGround Truth Changes: \n```\n{new}\n```"
    prompt += "\nDetailed Judgment Process:"
    prompt += "\nIdentify Differences in Code:Analyze the code block against the ground truth to ascertain modifications such as lines added, deleted, or altered."
    prompt += "\nAssess if any code elements mentioned in the comment or the ground truth (e.g., functions, variables) are absent from the provided code block and are not part of Python’s built-in functionalities."
    prompt += "\nAssess New Code Elements:Check if the modifications or additions in the code introduce new code elements specific to the repository, excluding comments and natural language elements. These elements should be defined within the repository but not present in the provided code snippet."
    prompt += "\nCorrelate Reviewer’s Comments:Determine if the reviewer’s comment guides these modifications by mentioning new code elements not present in the code block, indicating potential missing context."
    prompt += "\nNecessity of Additional Context:Critically evaluate whether knowledge of these new code elements is essential to modify the code block to match the ground truth. Most new elements might not be useful; only consider additional context necessary if:"
    prompt += "\nThe implementation of these elements directly affects the proposed code changes."
    prompt += "\nThe reviewer’s comment explicitly mentions utilizing a function or method from the repository that influences the code changes significantly, such as function returns, parameters, or specific handling relevant to the code change."
    prompt += "\nOutput Requirements:"
    prompt += "\nProvide a structured evaluation in JSON format, detailing the necessity for additional context and specifying any elements that must be investigated:"
    prompt += "\n{\"Additional_context_required\": \"Enter 1 (yes) if project-specific knowledge is needed, or 0 (no) if not\",\"Function_name_to_retrieve\": \"List any project-specific functions or variables that need to be retrieved\",\"Reason_for_additional_context\": \"Explain why these specific repository elements are critical for the modification, supported by a detailed analysis of the code differences and reviewer’s guidance.\"}"
    return prompt

def prompt_for_context_requirement(old, review):
    prompt = "\nTask Prompt for Evaluating Code Review Comments:"
    prompt += "\nAs an experienced human evaluator, you receive a reviewer's comment on a specific piece of code that requires modification. Your task involves a thoughtful step-by-step approach to consider the proposed changes. Begin by examining the provided code block and the reviewer’s comment to determine if the intended modifications can be achieved by editing the code in-place."
    prompt += "\nInstructions:"
    prompt += "Review the Comment and Code Block:"
    prompt += f"\nComment Provided: {review}"
    prompt += f"\nAssociated Code Block:\n```\n{old}\n```"
    prompt += "\nMake Two Key Judgments:"
    prompt += "\n1.Feasibility: Determine if the proposed changes are feasible within the given code block alone. Consider if the comment:"
    prompt += "\nReferences elements not included in the code block, which would imply that in-place modification is insufficient."
    prompt += "\nIs clear and specific enough to guide your modifications confidently. If the comment is vague or lacks direction, it may not inspire a successful modification."
    prompt += "\n2.Additional Context Requirements: Decide if additional context from outside the given code snippet is needed to properly implement the changes. This may involve:"
    prompt += "\nExternal functions or variables mentioned but not defined within the code block."
    prompt += "\nSpecific files or repository knowledge that could influence the modification."
    prompt += "\nOutput Requirements: Provide your analysis in a JSON format detailing your conclusions on feasibility and the need for additional context:"
    prompt += "\n```{\"Feasibility\": \"Enter 1 (feasible) or 0 (not feasible)\",\"Reason_for_feasibility\": \"Explain why the modification is feasible or not based on the code block and comment clarity.\",\"Additional_context_required\": \"Enter 1 (yes) or 0 (no)\",\"Reason_for_additional_context\": \"Describe why additional context is needed or not, including specific elements or information required for modification.\"}```"
    prompt += "\nNote: Your responses should be direct and supported by specific observations from the reviewer's comment and the code snippet. Your goal is to assess whether the changes suggested by the reviewer can be accomplished with the current information or if external details are necessary.Your response should only include the json object with four keys and their corresponding values."
    return prompt

def prompt_for_quality_estimation(old, review, new):
    prompt = "\nTask:"
    prompt += "\nYou are an experienced code quality evaluator. Classify the given dataset instance (Old code, Review, New code) as valid or discarded based on strict rules."
    prompt += "\nClassification Criteria (mark as discarded if ANY condition is met):"
    prompt += "\nUnclear Review: The Review is too vague for humans to infer the required change (e.g., \"Fix this\" without context)."
    prompt += "\nNo Change Asked: The Review is not requesting any change (e.g., “Awesome work so far, Eli!”)"
    prompt += "\nIgnored Review: Code changes deviate from the Review’s intent (e.g., Review requests a bug fix, but new features are added)."
    prompt += "\nWrong Linking: Old code has been linked to a wrong New code while mining the dataset."
    prompt += "\nEvaluation Steps:"
    prompt += "\nCheck Review Intent: Does the Review explicitly request a code change? If not (e.g., praise or no actionable request), mark discarded."
    prompt += "\nAssess Review Clarity: Is the Review specific enough to infer what to modify? If unclear (e.g., \"Improve this\"), mark discarded."
    prompt += "\nVerify Modification Alignment: Does the New code directly address the Review’s request? If changes ignore or contradict the Review, mark discarded."
    prompt += "\nValidate Code Relevance: Are Old and New code logically linked (e.g., same function/variable scope)? If unrelated, mark discarded."
    prompt += "\nInput Format for Classification:"
    prompt += "\nClassify the following dataset instance:"
    prompt += f"\nOld code: \n```\n{old}\n```"
    prompt += f"\nReview: \n```\n{review}\n```"
    prompt += f"\nNew code: \n```\n{new}\n```"
    prompt += "\nOutput Format:"
    prompt += "\nOnly respond with valid or discarded. No explanations."
    return prompt

def prompt_for_additional_context_required_estimation(old: str, review: str) -> str:
    prompt = "\nTask Prompt for Determining the Necessity of Additional Context in Code Refinement:"
    prompt += "\nYou are assigned the task of refining code based on a reviewer’s comment and a provided code diff block."
    prompt += "\nHowever, in real-world code review scenarios, reviewers often rely on additional repository-level context to make informed decisions."
    prompt += "\nThis task is designed to help determine whether such additional context is necessary in order to accurately implement the suggested changes."

    prompt += "\n\nDefinitions:"
    prompt += "\n- In-file context: Information from other parts of the same file as the code block, e.g., checking whether a function is used elsewhere before deleting it."
    prompt += "\n- Cross-file context: Information from other files in the repository, such as the definition of a varieble/function/class/module referenced but not shown in the current code block."

    prompt += "\n\nTask Inputs:"
    prompt += f"\nReviewer’s Comment:\n```\n{review}\n```"
    prompt += f"\nCode Block:\n```\n{old}\n```"

    prompt += "\n\nYour Judging Instructions:"
    prompt += "\nClassify the intent and specificity of the reviewer’s comment based on the following cases:"
    prompt += "\n   - Case 1: Clear attitude + Concrete modification → No additional context likely required."
    prompt += "\n   - Case 2: Unclear attitude + Concrete modification → Guess the intent and assess if context would help resolve ambiguity."
    prompt += "\n   - Case 3: Clear attitude + Vague modification → Assess if understanding the definition/usage of certain elements from other parts of the codebase would help refine the code."
    prompt += "\n   - Case 4: Unclear attitude + Vague modification → Combine case 2 & 3; if additional context cannot help, treat as no context required."
    prompt += "\n   - Case 5: No attitude or modification provided → Treat as no context required."

    prompt += "\n\nOutput Format (in JSON):"
    prompt += "\n- If additional context is NOT required:"
    prompt += "\n```json"
    prompt += "\n{\"Additional_context_required\": 0, \"Reason\": \"<Short explanation>\"}"
    prompt += "\n```"
    prompt += "\n- If additional context IS required:"
    prompt += "\n```json"
    prompt += "\n{"
    prompt += "\n  \"Additional_context_required\": 1,"
    prompt += "\n  \"Reason\": \"<Why additional context is needed>\","
    prompt += "\n  \"In_file_context_required\": 0 or 1,"
    prompt += "\n  \"Purpose_to_retrieve_in_file_context\": \"In no more than 50 words, describe what issue or uncertainty in the reviewer’s comment can be resolved by examining other parts of the same file.\","
    prompt += "\n  \"Cross_file_context_required\": 0 or 1"
    prompt += "\n}"
    prompt += "\n```"

    return prompt

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
    prompt = "Task Prompt for Evaluating Additional Context Requirements in Code Review:"
    prompt += "\nAs an experienced evaluator, your primary task is to determine whether additional context is necessary to correctly revise the code based on the intentions expressed in the reviewer's comment. "
    prompt += "\nInstructions:"
    prompt += "\nReview the Provided Information:"
    if not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else: prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review
    prompt += f"\nAssociated Code Block: \n```\n{old_without_minus}\n```"
    if len(calls) > 0:
        prompt += "\nRepository Context:"
        prompt += "\nBased on the review, you checked the source code and find that :"
        for call in calls:
            caller, callee, callee_text, callee_context, callee_purpose = call
            callee_text_list = callee_text.split('\n')
            if len(callee_text_list) > 40:
                concise_callee_text = ""
                concise_callee_text += callee_text_list[0] + "\n"
                for callee_text_line in callee_text_list[1:]:
                    if callee_text_line.find("def") != -1 :
                        concise_callee_text += callee_text_line + "\n"
            if caller == callee or caller == "default_function": 
                if len(callee_text_list) > 40:
                    prompt += f"\nThe concise definition of \n{callee} is:\n```\n{concise_callee_text}\n``` "
                else:
                    prompt += f"\n{callee} is defined as:\n```\n{callee_text}\n```"
            else :
                if len(callee_text_list) > 40:
                    prompt += f"\n{caller} calls {callee}, and the concise definition of {callee} is:\n```\n{concise_callee_text}\n``` "
                else:
                    prompt += f"\n{caller} calls {callee} which is defined as:\n```\n{callee_text}\n```"
    prompt += "\nDetailed Judgment Process:"
    prompt += "\nAssess the Intent of the Reviewer’s Comment:Analyze the intent behind the reviewer’s comment. Determine what specific actions are suggested to be performed on the code block to align with the reviewer's suggestions."
    prompt += "\nAssess Absent Repository Context:"
    prompt += f"\nIdentify any code elements such as functions, variables, or other significant items mentioned in the reviewer's comment or implied by the required modifications that are not detailed in the provided code block"
    if len(calls) > 0: prompt += " or current repository context." 
    else: prompt += "."
    prompt += "\nEvaluate whether knowing the implementation of these elements could help in understanding how to address the reviewer’s comments or how to modify the code. Consider if insights into these elements' parameters, functionality, return values, or execution processes are necessary."
    prompt += "\nOutput Requirements:"
    prompt += "\nProvide your evaluation in JSON format, detailing whether additional context is required and specifying which elements need further investigation:"
    prompt += "\n{\n\"Additional_context_required\": \"Enter 1 (yes) if project-specific knowledge is essential, or 0 (no) if not\",\n\"Element_name_to_retrieve\": \"List the most important project-specific function or variable that need to be retrieved\",\n\"Details_to_retrieve\": \"A sentence less than 50 words to specify what information is needed from the element, such as function parameters, purpose, return values, operations performed.And explain why it is important to retrieve this information.\"}"
    return prompt

def prompt_for_refinement(old_without_minus, review, calls, review_info, with_summary_or_code, with_presice_review_position, clipped_flag, in_file_context_summary):
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
    if in_file_context_summary:
        prompt += "\nBased on the review, you checked the file where the old code is located and find that:"
        prompt += "\n```\n{}\n```\n".format(in_file_context_summary)
    if len(calls) > 0:
        prompt += "\nBased on the review, you checked the repository and find that :\n"
        if with_summary_or_code == 'summary':
            prompt += calls[-1][3]
        else:
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

def prompt_for_context(text):
    prompt = ""
    prompt += "Try to summarize the class or function about the following text, your summary should include at least"\
              " the return type and main purpose with no more than 100 words."\
              "format your response as Summary: <Your Summary>\n"
    prompt += "```\n{}\n```\n".format(text)
    return prompt

def prompt_for_summary(review, calls):

    prompt = "\nTask Prompt for Summarizing Context in Code Review Based on Function Calls:"
    prompt += "\nAs an experienced software developer, you have received a code review comment that necessitates changes in your code."
    prompt += "\nTo fully understand the comment and refine your code, you searched the repository for implementations related to the functions or variables mentioned in your code changes and comments."
    prompt += "\nNow, your task is to summarize all relevant context information from these function calls, which are critical to implementing the suggested changes effectively."
    
    prompt += "\n\nInstructions:"
    prompt += f"\nReviewer's Comment: \n```\n{review}\n```"
    for i, call in enumerate(calls, start=1):
        if call[0] == call[1]:
            prompt += f"\nCallee {i}: {call[0]}\n```"
        else: prompt += f"\nCall {i}: {call[0]} calls {call[1]}"
        prompt += f"\nCallee Implementation: \n```\n{call[2]}\n```"
        prompt += f"\nPurpose to Check This Callee: {call[4]}"

    prompt += "\nDetailed Reasoning and Analysis Process:"
    prompt += "\nStep 1: Analyze the reviewer's comment to infer the intended modifications or concerns."
    prompt += "\nStep 2: Examine each function call to determine its relevance and potential impact on the proposed changes, focusing on why each function's specific characteristics are significant for the code's adaptation."
    prompt += "\n\nOutput Requirements:"
    prompt += "\nProvide a concise and targeted summary less than 100 words as a response to the requirements about the relevant context information."
    prompt += "\nFocus on information that directly supports the necessary code changes, highlighting how each detail aids in achieving the code review's goals."
    prompt += "\nFormat your response as a JSON object: {\"Summary\": <Your Summary>}"

    return prompt

def prompt_for_in_file_context_summary(review, in_file_context, purpose):

    prompt = "\nTask Prompt for Summarizing In-File Context in Code Review Based on Function Calls:"
    prompt += "\nAs an experienced software developer, you have received a code review comment that necessitates changes in your code."
    prompt += "\nTo fully understand the comment and refine your code, you retrieved the in-file context, specifically the entire source code where the previous code changes are located."
    prompt += "\nIn-file context is information from other parts of the same file as the code block. There are senarios where the in-file context is necessary for implementing the suggested changes effectively, e.g., checking whether a function is used elsewhere before deleting it."
    prompt += "\nNow, your task is to summarize the in-file context and response to the purpose for retrieving the context."
    
    prompt += "\n\nInstructions:"
    prompt += f"\nReviewer's Comment: \n```\n{review}\n```"
    prompt += f"\nPurpose to Retrieve In-File Context: \n```\n{purpose}\n```"
    prompt += f"\nIn-File Context: \n```\n{in_file_context}\n```"
    
    prompt += "\nDetailed Reasoning and Analysis Process:"
    prompt += "\nStep 1: Analyze the reviewer's comment to infer the intended modifications or concerns."
    prompt += "\nStep 2: Summarize the in-file context and response to the purpose for retrieving the context."
    prompt += "\n\nOutput Requirements:"
    prompt += "\nProvide a concise and targeted summary less than 100 words as a response to the requirements about the in-file context information."
    prompt += "\nFocus on information that directly supports the necessary code changes, highlighting how each detail aids in achieving the code review's goals."
    prompt += "\nFormat your response as a JSON object: {\"Summary\": <Your Summary>}"

    return prompt

def get_model_response(prompt,temperature=0):
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