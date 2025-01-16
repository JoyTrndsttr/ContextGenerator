# 数据库连接配置
from time import sleep
import psycopg2
import json
from openai import OpenAI
from evaluation import myeval
from utils.RequestModel import OpenAIUtils
import re
import logging

db_config = {
    'dbname': 'HCGGraph',
    'user': 'user',
    'password': '123456',
    'host': 'localhost',
    'port': '5432'
}

generation_kwargs = {
    "max_tokens": 1000,
    "temperature": 1,
    "top_p": 0.95,
    "n": 1,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0
}

model = OpenAIUtils(model_id="llama:7b", generation_kwargs=generation_kwargs)
logging.basicConfig(filename='log.txt', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

def get_context_explanation():
    sample_context = [{"Call_name": "func1","Call_path": "<path_to_func1>.func1","Call_text": "<func_content>","Call_type": "<type>"}]
    context_prompt = "\nConsider a context:" + json.dumps(sample_context)
    context_prompt += "It indicates that <path_to_func1>.func1 was called , which is of type <type>, with specific content <func_content>\n"
    return context_prompt

def get_db_ids():
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT _id from cacr_py where context is not null order by _id ASC")
    while True:
        record = cursor.fetchone()
        if record is None:
            break
        yield record

def get_db_info(id):
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT _id, old, new, review, context FROM cacr_py WHERE _id = %s;", [id])
    record = cursor.fetchone()
    conn.close()
    return record

#精简context
def get_concise_context(old, context):
    context_data = json.loads(context)
    _context = []

    # 遍历每个文件路径和其中的函数调用
    for file_path, calls in context_data.items():
        for method, details in calls.items():
            for call in details:
                call_name = call["Call_name"]
                # 检查old字符串中是否包含当前的函数调用名
                if call_name in old:
                    # 确保相同的函数调用名（Call_name）不重复
                    if not any(c["Call_name"] == call_name for c in _context):
                        _context.append({
                            "Call_name": call["Call_name"],
                            "Call_path": call["Call_path"],
                            "Call_text": call["Call_text"],
                            "Call_type": call["Call_type"]
                        })
    return _context

def get_few_shot_prompt():
    prompt = "There is a example about the format of the revised code:\n"
    old_code_string = "            code.putln(\"#if !CYTHON_COMPILING_IN_LIMITED_API\") \n            # FIXME: these still need to get initialised even with the limited-API\n            for slot in TypeSlots.get_slot_table(code.globalstate.directives).slot_table:\n                slot.generate_dynamic_init_code(scope, code)\n            code.putln(\"#endif\")"
    new_code_string = "            code.putln(\"#if !CYTHON_COMPILING_IN_LIMITED_API\") \n            # FIXME: these still need to get initialised even with the limited-API\n            for slot in TypeSlots.get_slot_table(code.globalstate.directives): \n                slot.generate_dynamic_init_code(scope, code)\n            code.putln(\"#endif\")"
    context = [{'Call_name': 'get_slot_table', 'Call_path': 'Cython.Compiler.TypeSlots.get_slot_table', 'Call_text': 'def get_slot_table(compiler_directives):\n    # use "get" here with a default since the builtin type classes don\'t have\n    # directives set\n    old_binops = compiler_directives.get(\'c_api_binop_methods\', False)\n    key = (old_binops,)\n    if key not in _slot_table_dict:\n        _slot_table_dict[key] = SlotTable(old_binops=old_binops)\n    return _slot_table_dict[key]\n', 'Call_type': 'function'}, {'Call_name': 'slot', 'Call_path': 'Cython.Compiler.ModuleNode.ModuleNode.generate_typeobj_spec.slot', 'Call_text': '        for slot in TypeSlots.get_slot_table(code.globalstate.directives).slot_table:\n            slot.generate_spec(scope, code)', 'Call_type': 'statement'}, {'Call_name': 'scope', 'Call_path': 'Cython.Compiler.ModuleNode.ModuleNode.generate_typeobj_spec.scope', 'Call_text': '        scope = ext_type.scope\n', 'Call_type': 'statement'}, {'Call_name': 'generate', 'Call_path': 'Cython.Compiler.TypeSlots.SlotDescriptor.generate', 'Call_text': '    def generate(self, scope, code):\n        preprocessor_guard = self.preprocessor_guard_code()\n        if preprocessor_guard:\n            code.putln(preprocessor_guard)\n\n        end_pypy_guard = False\n        if self.is_initialised_dynamically:\n            value = "0"\n        else:\n            value = self.slot_code(scope)\n            if value == "0" and self.is_inherited:\n                # PyPy currently has a broken PyType_Ready() that fails to\n                # inherit some slots.  To work around this, we explicitly\n                # set inherited slots here, but only in PyPy since CPython\n                # handles this better than we do (except for buffer slots in type specs).\n                inherited_value = value\n                current_scope = scope\n                while (inherited_value == "0"\n                       and current_scope.parent_type\n                       and current_scope.parent_type.base_type\n                       and current_scope.parent_type.base_type.scope):\n                    current_scope = current_scope.parent_type.base_type.scope\n                    inherited_value = self.slot_code(current_scope)\n                if inherited_value != "0":\n                    # we always need inherited buffer slots for the type spec\n                    is_buffer_slot = int(self.slot_name in ("bf_getbuffer", "bf_releasebuffer"))\n                    code.putln("#if CYTHON_COMPILING_IN_PYPY || %d" % is_buffer_slot)\n                    code.putln("%s, /*%s*/" % (inherited_value, self.slot_name))\n                    code.putln("#else")\n                    end_pypy_guard = True\n\n        code.putln("%s, /*%s*/" % (value, self.slot_name))\n\n        if end_pypy_guard:\n            code.putln("#endif")\n\n        if self.py3 == \'<RESERVED>\':\n            code.putln("#else")\n            code.putln("0, /*reserved*/")\n        if preprocessor_guard:\n            code.putln("#endif")\n', 'Call_type': 'function'}, {'Call_name': 'generate_dynamic_init_code', 'Call_path': 'Cython.Compiler.TypeSlots.SlotDescriptor.generate_dynamic_init_code', 'Call_text': '    def generate_dynamic_init_code(self, scope, code):\n        if self.is_initialised_dynamically:\n            self.generate_set_slot_code(\n                self.slot_code(scope), scope, code)\n', 'Call_type': 'function'}]
    review_string   = "I wonder if the `SlotTable` should just be iterable.\n"
    prompt += f"Given old code:\n{old_code_string}\n"
    prompt += f"Given review:\n{review_string}\n"
    prompt += f"Given context:{context}\n"
    prompt += "\nYou might be able to get the information from the context that a SlotTable object is returned in the get_slot_table method, just delete the .slot_table to avoid redundancy based on the content of the review.\n"
    prompt += f"Your revised code should follow the format of old code which is:\n{new_code_string}\n"
    prompt += "Prompt above is just a example about the format of the revised code and do not output anything about it.Focus on the following task.\n"
    return prompt

# def few_shot_prompt(sample=[1585,6248,6396]):
#     prompt = "There are samples about code_diff to review:\n"
#     for id in sample:
#         record_id, repo, commit_hash, pr_id, review ,path, code_diff, context = get_db_info(id)
#         prompt += f"code_diff:{code_diff};\nreview:{review}\n"
#     return prompt

#generate comments
# def generate_review_prompt(code_diff, context):
#     '''
#     Given a code diff and its context, generate a prompt for writing a concise and precise code review.
#     '''
#     prompt = "As a reviewer, you are examining a proposed code change in a pull request. "
#     prompt += "You have the following code changes:\n"
#     prompt += "```\n{}\n```\n".format(code_diff)
#     prompt += "And the context provided with the changes is:\n"
#     prompt += "```\n{}\n```\n".format(context)
#     prompt += "Based on the code changes and the context, please provide a concise and precise review. "
#     prompt += "Only output the review,which should be no more than 3 sentences within 30 words."
#     prompt += "The review needs to mimic human tone and be centred around only one point.\n"
#     prompt += few_shot_prompt([1585,6248,6396])
#     print(prompt)
#     return prompt


def generate_new_prompt1(old_without_minus, review, context):
    '''
     the simplest prompt
    '''
    prompt = ""
    prompt += "code snippet:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    prompt += "code review:\n"
    prompt += review
    prompt += "Given context:\n"
    prompt += context
    prompt += "\nPlease generate the revised code according to the review and the context"
    return prompt
def generate_new_prompt2(old_without_minus, review, context):
    '''
    P1 + Scenario Description.
    '''
    prompt = ""
    prompt += "As a developer, imagine you've submitted a pull request and" \
              " your team leader requests you to make a change to a piece of code." \
              " The old code being referred to in the hunk of code changes is:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    prompt += "There is the code review for this code:\n"
    prompt += review
    prompt += "\nThere is context about function call:"
    prompt += context
    prompt += "\nPlease generate the revised code according to the review"
    return prompt
def generate_new_prompt3(old_without_minus, review, context):
    '''
    P1 + Few Shot Prompt + Scenario Description.
    '''
    prompt = ""
    prompt += get_few_shot_prompt()
    prompt += "As a developer, imagine you've submitted a pull request and" \
              " your team leader requests you to make a change to a piece of code." \
              " The old code being referred to in the hunk of code changes is:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    prompt += "There is the code review for this code:\n"
    prompt += review
    prompt += "\nThere is context about function call:"
    prompt += context
    prompt += "\nPlease generate the revised code according to the review"
    return prompt
def generate_new_prompt4(old_without_minus, review, context):
    '''
    P1 + Scenario Description + Context Explanation.
    '''
    prompt = ""
    prompt += "As a developer, imagine you've submitted a pull request and" \
              " your team leader requests you to make a change to a piece of code." \
              " The old code being referred to in the hunk of code changes is:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    prompt += "There is the code review for this code:\n"
    prompt += review
    # prompt += get_context_explanation()
    if len(context) > 0:
        prompt += "Based on the review,we provide the following context about function code:"
        prompt += context
    prompt += "\nPlease generate the revised code according to the review. " \
              "Please ensure that the revised code follows the original code format" \
              " and comments, unless it is explicitly required by the review."
    return prompt
def generate_new_prompt5(old_without_minus, review, context):
    '''
    P1 + Few Shot Prompt + Scenario Description + Context Explanation.
    '''
    prompt = ""
    prompt += get_few_shot_prompt()
    prompt += "\nAs a developer, imagine you've submitted a pull request and" \
              " your team leader requests you to make a change to a piece of code." \
              " The old code being referred to in the hunk of code changes is:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    prompt += "There is the code review for this code:\n"
    prompt += review
    prompt += get_context_explanation()
    prompt += "There is context about function call:"
    prompt += context
    prompt += "\nPlease generate the revised code according to the review."
    return prompt
def generate_new_prompt5_CRN(old_without_minus, review, context):
    '''
    P4 + Scenario Description.
    '''
    prompt = ""
    prompt += "As a developer, imagine you've submitted a pull request and" \
              " your team leader requests you to make a change to a piece of code." \
              " The old code being referred to in the hunk of code changes is:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    prompt += "There is the code review for this code:\n"
    prompt += review
    prompt += "\nPlease generate the revised code according to the review. " \
              "Please ensure that the revised code follows the original code format" \
              " and comments, unless it is explicitly required by the review."
    return prompt


# def generate_context_prompt(old_without_minus, review):

#     prompt = "As a developer, your pull request receives a reviewer's comment on " \
#               "a specific piece of code that requires a change.In order to make " \
#               "changes based on the review,you need to refer back to the original code. " \
#               "You should provide the code implementation of which function you'd most "\
#               "like to refer to.\n"
#     prompt += "The old code being referred to in the hunk of code changes is:\n"
#     prompt += "```\n{}\n```\n".format(old_without_minus)
#     prompt += "The code review for this code is:\n"
#     prompt += review
#     prompt += "\nIf you need more information to generate the new code, provide the name from the old code and explain why you chose it. Format your response as a JSON object:```{ 'Need more information?': <True/False>, 'function_name': '<function_name>', 'reason': '<reason>' }```"
#     return prompt

def prompt_for_instruction(old_without_minus, review, calls, turn, review_info, name_list):
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
    prompt += "\nPlease provide the name appears in the source code that have not yet been checked  and explain why you chose it. Format your response"\
              " as a JSON object:```{ \"function_name\": \"<function_name>\", \"reason\": \"<reason>\" }```"
    return prompt

def prompt_for_refinement(old_without_minus, review, calls, reason, turn, review_info, with_summary_or_code, with_consice_review_position):
    prompt = ""
    prompt += "As a developer, imagine you've submitted a pull request and" \
              " your team leader requests you to make a change to a piece of code." \
              " The old code being referred to in the hunk of code changes is:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    if not with_consice_review_position or not review_info or not review_info.get("review_position_line", None):
        prompt += "The code review for this code is:\n"
    else:
        if review_info.get("review_hunk_start_line", None):
            prompt += f"The reviewer commented on the code from line '{review_info['review_hunk_start_line']}' to line '{review_info['review_position_line']}':\n"
        else: prompt += f"The reviewer commented on the line '{review_info['review_position_line']}':\n"
    prompt += review
    if len(calls) > 0:
        if not reason:
            prompt += "\nBased on the review, you checked the source code and find that :"
        else:
            prompt += f"\nBased on the review, you checked the source code and find that:{reason}."
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
                prompt += f"\n{caller} calls {signature}, and the detail information of {signature} is: \n{main_purpose}"
    prompt += "\nPlease generate the revised code according to the review. " \
              "Please ensure that the revised code follows the original code format" \
              " and comments, unless it is explicitly required by the review."
    if len(calls) > 0:
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

def generate_context_prompt(old_without_minus, review, context):

    prompt = "As a developer, your pull request receives a reviewer's comment on " \
              "a specific piece of code that requires a change.In order to make " \
              "changes based on the review,you need to refer back to the original code. " \
              "You should provide the code implementation of which function you'd most "\
              "like to refer to.\n"
    prompt += "The old code being referred to in the hunk of code changes is:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    prompt += "The code review for this code is:\n"
    prompt += review
    if context:
        prompt += "\nHere is the context json string about the old code:\n"
        prompt += context
    # prompt += "If you need more information to generate the new code, provide the function, class, or variable name from the old code you want to reference. Also, indicate where it's used (line and column) and explain why you chose it. Format your response as a JSON object:```{ 'Need more information?': <True/False>, 'function_name': '<function_name>', 'cursor': (<line_number>, <column_number>), 'reason': '<reason>' }```"
    prompt += "\nIf you need more information to generate the new code, provide the name from the context json string and explain why you chose it. Format your response as a JSON object:```{ 'Need more information?': <True/False>, 'function_name': '<function_name>', 'reason': '<reason>' }```"
    # prompt += get_few_shot_prompt()
    return prompt

def get_model_response(prompt,temperature=1.0):
    answer = model.get_completion([prompt])
    result = re.search(r'```(.*)```', answer,re.DOTALL)
    print(f"prompt:\n{prompt}\nanswer:\n{answer}")
    if result: # TODO 由于模型可能会受到提示词的干扰，应该选表现最好的newcode
        newcode = result.group(1)
    return newcode if result else "", answer

def store_result(_id, em, em_trim, bleu, bleu_trim, type):
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    if type == 'CACR':
        cursor.execute("""
            UPDATE cacr_py
            SET gpt_with_context_em = %s, gpt_with_context_em_trim = %s, gpt_with_context_bleu = %s, gpt_with_context_bleu_trim = %s
            WHERE _id = %s;
        """, (em, em_trim, bleu, bleu_trim, _id))
    else:
        cursor.execute("""
            UPDATE cacr_py
            SET gpt_em_new = %s, gpt_em_trim_new = %s, gpt_bleu_new = %s, gpt_bleu_trim_new = %s
            WHERE _id = %s;
        """, (em, em_trim, bleu, bleu_trim, _id))
    conn.commit()
    cursor.close()
    conn.close()

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

def main(id):
    record = get_db_info(id)
    if record:
        _id, old, new, review, context = record
        context = json.dumps(get_concise_context(old, context))
        old_without_minus = remove_minus_or_plus(old, "-")
        new_without_plus = remove_minus_or_plus(new, "+")
        prompt_for_get_function_name = generate_context_prompt(old_without_minus, review)
        newcode, result = get_model_response(prompt_for_get_function_name)

        try:
            funcName_for_research = json.loads(newcode)["function_name"]
        except Exception as e:
            print(e)
            funcName_for_research = ""
        print(f"funcName_for_research: {funcName_for_research}")
        print(result)

        concise_context = []
        if not funcName_for_research=="":
            _context = json.loads(context)
            for item in _context:
                if re.search(funcName_for_research, item["Call_name"]):
                    concise_context.append(item)
        
        best_llama_em, best_llama_em_trim, best_llama_bleu, best_llama_bleu_trim, best_llama_newcode = 0, 0, 0, 0, ""
        i = 0
        while i < 2:
            i += 1
            prompt4 = generate_new_prompt4(old_without_minus, review, json.dumps(concise_context))
            llama_newcode, llama_result = get_model_response(prompt4)
            llama_em, llama_em_trim, _, _, llama_bleu, llama_bleu_trim \
                = myeval(new_without_plus, llama_newcode)
            if llama_bleu_trim > best_llama_bleu_trim:
                best_llama_em, best_llama_em_trim, best_llama_bleu, best_llama_bleu_trim, best_llama_newcode = llama_em, llama_em_trim, llama_bleu, llama_bleu_trim, llama_newcode

        best_crn_em, best_crn_em_trim, best_crn_bleu, best_crn_bleu_trim = 0, 0, 0, 0
        i = 0
        while i < 2:
            i += 1
            prompt_CRN = generate_new_prompt5_CRN(old_without_minus, review, context)
            crn_newcode, crn_result = get_model_response(prompt_CRN)
            crn_em, crn_em_trim, _, _, crn_bleu, crn_bleu_trim \
                = myeval(new_without_plus, crn_newcode)
            if crn_bleu_trim > best_crn_bleu_trim:
                best_crn_em, best_crn_em_trim, best_crn_bleu, best_crn_bleu_trim = crn_em, crn_em_trim, crn_bleu, crn_bleu_trim
        
        data = {}
        data["id"] = _id
        data["old_code"] = old_without_minus
        data["new_code"] = new_without_plus
        data["code_review"] = review
        data["context"] = context
        data["prompt_for_get_function_name"] = prompt_for_get_function_name
        data["output_for_get_context_info"] = result
        data["funcName_for_research"] = funcName_for_research
        data["concise_context"] = concise_context
        data["prompt4"] = prompt4
        data["llama_newcode"] = best_llama_newcode
        data["llama_em"] = best_llama_em
        data["llama_em_trim"] = best_llama_em_trim
        data["llama_bleu"] = best_llama_bleu
        data["llama_bleu_trim"] = best_llama_bleu_trim
        data["crn_em"] = best_crn_em
        data["crn_em_trim"] = best_crn_em_trim
        data["crn_bleu"] = best_crn_bleu
        data["crn_bleu_trim"] = best_crn_bleu_trim
        return data

        # prompt1 = generate_new_prompt5(old_without_minus, review, context)
        # evaluate(id, prompt1, new, "CACR")
        # prompt2 = generate_new_prompt5_CRN(old_without_minus, review, context)
        # evaluate(id, prompt2, new, "CRN")
        # data = {}
        # data["instruction"] = generate_instruction(review, context)
        # data["input"] = old_without_minus
        # data["output"] = new_without_plus
        # data_json = json.dumps(data, ensure_ascii=False, indent=8)
        # return data_json

def evaluate_from_json_file(file_path):
    def load_results(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    result = load_results(file_path)
    total_llama_em = total_llama_em_trim = total_llama_bleu = total_llama_bleu_trim = 0
    total_crn_em = total_crn_em_trim = total_crn_bleu = total_crn_bleu_trim = 0
    count = 0
    
    for item in result:
        if not item["llama_newcode"]=="":  # 确保 llama_code 非空
            if not len(item["concise_context"]) == 0:
                total_llama_em += item.get("llama_em", 0)
                total_llama_em_trim += item.get("llama_em_trim", 0)
                total_llama_bleu += item.get("llama_bleu", 0)
                total_llama_bleu_trim += item.get("llama_bleu_trim", 0)
                total_crn_em += item.get("crn_em", 0)
                total_crn_em_trim += item.get("crn_em_trim", 0)
                total_crn_bleu += item.get("crn_bleu", 0)
                total_crn_bleu_trim += item.get("crn_bleu_trim", 0)
                if item.get("llama_bleu_trim", 0) < 10:
                    print(item["id"])
                count += 1
    print(f"count:{count}")
    average_llama_em = total_llama_em / count
    average_llama_em_trim = total_llama_em_trim / count
    average_llama_bleu = total_llama_bleu / count
    average_llama_bleu_trim = total_llama_bleu_trim / count
    average_crn_em = total_crn_em / count
    average_crn_em_trim = total_crn_em_trim / count
    average_crn_bleu = total_crn_bleu / count
    average_crn_bleu_trim = total_crn_bleu_trim / count
    print(f"Average LLAMA EM: {average_llama_em}")
    print(f"Average LLAMA EM Trim: {average_llama_em_trim}")
    print(f"Average CRN EM: {average_crn_em}")
    print(f"Average CRN EM Trim: {average_crn_em_trim}")
    print(f"Average LLAMA BLEU: {average_llama_bleu}")
    print(f"Average LLAMA BLEU Trim: {average_llama_bleu_trim}")
    print(f"Average CRN BLEU: {average_crn_bleu}")
    print(f"Average CRN BLEU Trim: {average_crn_bleu_trim}")

def evaluate_from_json_files():
    def load_results(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    result = load_results('dataset/valid_result6_1.json')
    final_results = []
    for item in result:
        llama_result = re.search(r'```(.*)```', item["model_output"], re.DOTALL)
        llama_code = llama_result.group(1) if llama_result else ""
        new_code = "\n".join([line[1:].strip() for line in item["output"].split("\n") if line.strip() != ""])
        gpt_em, gpt_em_trim, _, _, gpt_bleu, gpt_bleu_trim \
            = myeval(new_code, llama_code)
        final_results.append({
            "instruction": item["instruction"],
            "input": item["input"],
            "output": item["output"],
            "model_output": item["model_output"],  # 可以选择一个代表性的model_output
            "llama_code": llama_code,
            "gpt_em": gpt_em,
            "gpt_em_trim": gpt_em_trim,
            "gpt_bleu": gpt_bleu,
            "gpt_bleu_trim": gpt_bleu_trim
        })
    with open('dataset/valid_evaluate_result_6.json', 'w', encoding='utf-8') as file:
        json.dump(final_results, file, indent=4, ensure_ascii=False)
    with open('dataset/valid_evaluate_result_6.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    total_bleu = 0
    total_bleu_trim = 0
    count = 0
    for item in data:
        if item.get("llama_code", "").strip():  # 确保 llama_code 非空
            bleu = item.get("gpt_bleu", 0)
            bleu_trim = item.get("gpt_bleu_trim", 0)
            if bleu_trim< 10:
                print(item.get("input"))
            total_bleu += item.get("gpt_bleu", 0)
            total_bleu_trim += item.get("gpt_bleu_trim", 0)
            print(f"bleu:{bleu} bleu_trim:{bleu_trim}")
            count += 1
    average_bleu = total_bleu / count
    average_bleu_trim = total_bleu_trim / count
    print(f"Average GPT BLEU: {average_bleu}")
    print(f"Average GPT BLEU Trim: {average_bleu_trim}")

def evaluate_from_mul_json_files():
    def load_results(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    results1 = load_results('dataset/valid_result5_1.json')
    results2 = load_results('dataset/valid_result5_2.json')
    results3 = load_results('dataset/valid_result5_3.json')
    final_results = []
    id = 0
    for item1, item2, item3 in zip(results1, results2, results3):
        best_em = best_em_trim = best_bleu = best_bleu_trim = 0
        best_llama_code = ""
        for item in [item1, item2, item3]:
            llama_result = re.search(r'```(.*)```', item["model_output"], re.DOTALL)
            llama_code = llama_result.group(1) if llama_result else ""

            new_code = "\n".join([line[1:].strip() for line in item["output"].split("\n") if line.strip() != ""])

            gpt_em, gpt_em_trim, _, _, gpt_bleu, gpt_bleu_trim \
                = myeval(new_code, llama_code)

            # 更新最好的指标值
            if gpt_em > best_em:
                best_em = gpt_em
            if gpt_em_trim > best_em_trim:
                best_em_trim = gpt_em_trim
            if gpt_bleu > best_bleu:
                best_bleu = gpt_bleu
            if gpt_bleu_trim > best_bleu_trim:
                best_bleu_trim = gpt_bleu_trim
                best_llama_code = llama_code

        # 保存最好结果到final_results
        final_results.append({
            "instruction": item1["instruction"],
            "input": item1["input"],
            "output": item1["output"],
            "model_output": item1["model_output"],  # 可以选择一个代表性的model_output
            "llama_code": best_llama_code,
            "gpt_em": best_em,
            "gpt_em_trim": best_em_trim,
            "gpt_bleu": best_bleu,
            "gpt_bleu_trim": best_bleu_trim
        })

    with open('dataset/valid_evaluate_result4.json', 'w', encoding='utf-8') as file:
        json.dump(final_results, file, indent=4, ensure_ascii=False)

    with open('dataset/valid_evaluate_result4.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    total_bleu = 0
    total_bleu_trim = 0
    count = 0
    for item in data:
        if item.get("llama_code", "").strip():  # 确保 llama_code 非空
            bleu = item.get("gpt_bleu", 0)
            bleu_trim = item.get("gpt_bleu_trim", 0)
            if bleu_trim< 10:
                print(item.get("input"))
                # continue
            total_bleu += item.get("gpt_bleu", 0)
            total_bleu_trim += item.get("gpt_bleu_trim", 0)
            print(f"bleu:{bleu} bleu_trim:{bleu_trim}")
            count += 1
    average_bleu = total_bleu / count
    average_bleu_trim = total_bleu_trim / count
    print(f"Average GPT BLEU: {average_bleu}")
    print(f"Average GPT BLEU Trim: {average_bleu_trim}")


if __name__ == "__main__":
    # for record in get_db_ids():
    #     id = record[0]
    #     if id > 4000 and id < 4100:
    #         main(id)
    # main(42)
    # evaluate_from_json_files()
    # evaluate_from_mul_json_files()

    # with open('dataset/data_cacr3.json', 'w', encoding='utf-8') as f:
    #     f.write("[\n    ")
    #     first_record = True
    #     for record in get_db_ids():
    #         id = record[0]
    #         logging.info(f'Processing {id}',exc_info=True)
    #         # if id > 4000 and id < 4100:
    #         # if id == 4071:
    #         if True:
    #             try:
    #                 print(f"processing:{id}")
    #                 if not first_record:
    #                     f.write(",\n    ")
    #                 f.write(json.dumps(main(id)))
    #                 first_record = False
    #             except Exception as e:
    #                 print(f"error, id:{id} {e}")
    #     f.write("\n]")
    evaluate_from_json_file('dataset/data_cacr3.json')

    # for record in get_db_ids():
    #     id = record[0]
    #     if id > 455:
    #         logging.info(f'Processing {id}',exc_info=True)
    #         for i in range(2):
    #             try:
    #                 main(id)
    #             except Exception as e:
    #                 print(f"error, id:{id} try the {i}th time:{e}")
    #                 sleep(5)
    #                 # if i >= 3:
    #                 #     for j in range(360):
    #                 #         print("waiting for manual stop or {}0s".format(360 - j))
    #                 #         with open('manual_stop.json', 'r') as f:
    #                 #             data = json.load(f)
    #                 #             if data["manual_stop"]:
    #                 #                 print("manual stop")
    #                 #                 # pdf.save()
    #                 #                 exit(0)
    #                 #         sleep(10)
    #                 continue
    #             break