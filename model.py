# 数据库连接配置
import psycopg2
import json
from openai import OpenAI
import re

db_config = {
    'dbname': 'HCGGraph',
    'user': 'user',
    'password': '123456',
    'host': 'localhost',
    'port': '5432'
}

def get_context_explanation():
    sample_context = {"a.b.py":{"c.d":[{"Call_name": "e","Call_path": "f.g","Call_text": "g","Call_type": "h"}]}}
    context_prompt = "Consider a context:" + json.dumps(sample_context)
    context_prompt += "It indicates that under the path a.b.py, there is a function c.d() that calls e of type h. The specific <h> content of e is g."
    return context_prompt

def get_db_info(id):
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT _id, old, new, code_diff, context FROM cacr_py WHERE _id = %s;", [id])
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
    prompt = "There is a example about the format of the revised code:"
    old_code_string = "            code.putln(\"#if !CYTHON_COMPILING_IN_LIMITED_API\") \n            # FIXME: these still need to get initialised even with the limited-API\n            for slot in TypeSlots.get_slot_table(code.globalstate.directives).slot_table:\n                slot.generate_dynamic_init_code(scope, code)\n            code.putln(\"#endif\")"
    new_code_string = "            code.putln(\"#if !CYTHON_COMPILING_IN_LIMITED_API\") \n            # FIXME: these still need to get initialised even with the limited-API\n            for slot in TypeSlots.get_slot_table(code.globalstate.directives): \n                slot.generate_dynamic_init_code(scope, code)\n            code.putln(\"#endif\")"
    context = [{'Call_name': 'get_slot_table', 'Call_path': 'Cython.Compiler.TypeSlots.get_slot_table', 'Call_text': 'def get_slot_table(compiler_directives):\n    # use "get" here with a default since the builtin type classes don\'t have\n    # directives set\n    old_binops = compiler_directives.get(\'c_api_binop_methods\', False)\n    key = (old_binops,)\n    if key not in _slot_table_dict:\n        _slot_table_dict[key] = SlotTable(old_binops=old_binops)\n    return _slot_table_dict[key]\n', 'Call_type': 'function'}, {'Call_name': 'slot', 'Call_path': 'Cython.Compiler.ModuleNode.ModuleNode.generate_typeobj_spec.slot', 'Call_text': '        for slot in TypeSlots.get_slot_table(code.globalstate.directives).slot_table:\n            slot.generate_spec(scope, code)', 'Call_type': 'statement'}, {'Call_name': 'scope', 'Call_path': 'Cython.Compiler.ModuleNode.ModuleNode.generate_typeobj_spec.scope', 'Call_text': '        scope = ext_type.scope\n', 'Call_type': 'statement'}, {'Call_name': 'generate', 'Call_path': 'Cython.Compiler.TypeSlots.SlotDescriptor.generate', 'Call_text': '    def generate(self, scope, code):\n        preprocessor_guard = self.preprocessor_guard_code()\n        if preprocessor_guard:\n            code.putln(preprocessor_guard)\n\n        end_pypy_guard = False\n        if self.is_initialised_dynamically:\n            value = "0"\n        else:\n            value = self.slot_code(scope)\n            if value == "0" and self.is_inherited:\n                # PyPy currently has a broken PyType_Ready() that fails to\n                # inherit some slots.  To work around this, we explicitly\n                # set inherited slots here, but only in PyPy since CPython\n                # handles this better than we do (except for buffer slots in type specs).\n                inherited_value = value\n                current_scope = scope\n                while (inherited_value == "0"\n                       and current_scope.parent_type\n                       and current_scope.parent_type.base_type\n                       and current_scope.parent_type.base_type.scope):\n                    current_scope = current_scope.parent_type.base_type.scope\n                    inherited_value = self.slot_code(current_scope)\n                if inherited_value != "0":\n                    # we always need inherited buffer slots for the type spec\n                    is_buffer_slot = int(self.slot_name in ("bf_getbuffer", "bf_releasebuffer"))\n                    code.putln("#if CYTHON_COMPILING_IN_PYPY || %d" % is_buffer_slot)\n                    code.putln("%s, /*%s*/" % (inherited_value, self.slot_name))\n                    code.putln("#else")\n                    end_pypy_guard = True\n\n        code.putln("%s, /*%s*/" % (value, self.slot_name))\n\n        if end_pypy_guard:\n            code.putln("#endif")\n\n        if self.py3 == \'<RESERVED>\':\n            code.putln("#else")\n            code.putln("0, /*reserved*/")\n        if preprocessor_guard:\n            code.putln("#endif")\n', 'Call_type': 'function'}, {'Call_name': 'generate_dynamic_init_code', 'Call_path': 'Cython.Compiler.TypeSlots.SlotDescriptor.generate_dynamic_init_code', 'Call_text': '    def generate_dynamic_init_code(self, scope, code):\n        if self.is_initialised_dynamically:\n            self.generate_set_slot_code(\n                self.slot_code(scope), scope, code)\n', 'Call_type': 'function'}]
    review_string   = "I wonder if the `SlotTable` should just be iterable."
    prompt += f"Given old code:{old_code_string}"
    prompt += f"Given review:{review_string}"
    prompt += f"Given context:{context}"
    prompt += "You might be able to get the information from the context that a SlotTable object is returned in the get_slot_table method, just delete the .slot_table to avoid redundancy based on the content of the review."
    prompt += f"Your revised code should follow the format of old code which is:{new_code_string}"
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
    prompt += "There is context about function call:"
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
    prompt += "There is context about function call:"
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
    prompt += "There is context about function call:"
    prompt += get_context_explanation()
    prompt += context
    prompt += "\nPlease generate the revised code according to the review"
    return prompt
def generate_new_prompt5(old_without_minus, review, context):
    '''
    P1 + Few Shot Prompt + Scenario Description + Context Explanation.
    '''
    prompt = ""
    prompt += get_few_shot_prompt()
    prompt += "As a developer, imagine you've submitted a pull request and" \
              " your team leader requests you to make a change to a piece of code." \
              " The old code being referred to in the hunk of code changes is:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    prompt += "There is the code review for this code:\n"
    prompt += review
    prompt += "There is context about function call:"
    prompt += get_context_explanation()
    prompt += context
    prompt += "\nPlease generate the revised code according to the review"
    return prompt
# def generate_new_prompt3(old_without_minus, review, context):
#     '''
#     P1 + Detailed Requirements.
#     '''
#     prompt = ""
#     prompt += "You will be provided with a partial code snippet,a code review message for" \
#               "the given code and the context about the function call details of the" \
#               " code snippet. Your task is to generate a revised code snippet based" \
#               " on the review message and the provided code. However, you should not complete" \
#               " the partial code. Your output should consist of changes, modifications," \
#               " deletions or additions to the provided code snippet that address the issues" \
#               " raised in the code review. Note that you are not required to write new code" \
#               " from scratch, but rather revise and improve the given code.\n"
#     prompt += get_few_shot_prompt()
#     prompt += "Provided partial code:\n```\n{}\n```\n".format(old_without_minus)
#     prompt += "Code review:\n"
#     prompt += review
#     prompt += get_context_explanation()
#     prompt += "There is context about the function call:"
#     prompt += context
#     prompt += "\nPlease generate the revised code."
#     return prompt
# def generate_new_prompt4(old_without_minus, review, context):
#     '''
#     P1 + Concise Requirements.
#     '''
#     prompt = ""
#     prompt += get_few_shot_prompt()
#     prompt += "code snippet:\n"
#     prompt += "```\n{}\n```\n".format(old_without_minus)
#     prompt += "code review:\n"
#     prompt += review
#     prompt += get_context_explanation()
#     prompt += "There is context about the function call:"
#     prompt += context
#     prompt += "\nPlease generate the revised code according to the review. " \
#               "Please ensure that the revised code follows the original code format" \
#               " and comments, unless it is explicitly required by the review."
#     return prompt
# def generate_new_prompt5(old_without_minus, review, context):
#     '''
#     P4 + Scenario Description.
#     '''
#     prompt = ""
#     prompt += get_few_shot_prompt()
#     prompt += "As a developer, imagine you've submitted a pull request and" \
#               " your team leader requests you to make a change to a piece of code." \
#               " The old code being referred to in the hunk of code changes is:\n"
#     prompt += "```\n{}\n```\n".format(old_without_minus)
#     prompt += "There is the code review for this code:\n"
#     prompt += review
#     prompt += get_context_explanation()
#     prompt += "There is context about the function call:"
#     prompt += context
#     prompt += "\nPlease generate the revised code according to the review. " \
#               "Please ensure that the revised code follows the original code format" \
#               " and comments, unless it is explicitly required by the review."
#     return prompt

def get_chatgptapi_response(prompt,temperature=1.0):
    client = OpenAI(
        api_key = json.load(open("settings.jsonl", encoding='utf-8'))["api_key"]
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # 确保使用正确的模型名称
        messages=[
            {"role": "system", "content": "You are an experienced developer."},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature
    )
    # print(response)
    answer = response.choices[0].message.content
    print("answer: ",answer)
    result = re.search(r'```(.*)```', answer,re.DOTALL)
    # print("result: ",result)
    if result:
        newcode = result.group(1)
        print(newcode)
    return ""

def main(id):
    record = get_db_info(id)
    if record:
        _id, old, new, code_diff, context = record
        context = json.dumps(get_concise_context(old, context))
        old_without_minus = [] #去除减号
        for line in old.split("\n"):
            if line.startswith('-'):
                old_without_minus.append(line[1:])
            else:
                old_without_minus.append(line)
        old_without_minus = "\n".join(old_without_minus)
        prompt = generate_new_prompt5(old_without_minus, code_diff, context)
        get_chatgptapi_response(prompt)

if __name__ == "__main__":
    main(4071)