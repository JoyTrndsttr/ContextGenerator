# 数据库连接配置
import psycopg2
from openai import OpenAI

db_config = {
    'dbname': 'HCGGraph',
    'user': 'user',
    'password': '123456',
    'host': 'localhost',
    'port': '5432'
}

def get_db_info(id):
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT id, repo, commit_hash, pr_id, review, path, code_diff, context FROM cacr WHERE id = %s;", [id])
    record = cursor.fetchone()
    conn.close()
    return record

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



def generate_new_prompt1(old_without_minus, review):
    '''
     the simplest prompt
    '''
    prompt = ""
    prompt += "code snippet:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    prompt += "code review:\n"
    prompt += review
    prompt += "\nPlease generate the revised code according to the review"
    return prompt
def generate_new_prompt2(old_without_minus, review):
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
    prompt += "\nPlease generate the revised code according to the review"
    return prompt
def generate_new_prompt3(old_without_minus, review):
    '''
    P1 + Detailed Requirements.
    '''
    prompt = ""
    prompt += "You will be provided with a partial code snippet and a code review message" \
              " for the given code. Your task is to generate a revised code snippet based" \
              " on the review message and the provided code. However, you should not complete" \
              " the partial code. Your output should consist of changes, modifications," \
              " deletions or additions to the provided code snippet that address the issues" \
              " raised in the code review. Note that you are not required to write new code" \
              " from scratch, but rather revise and improve the given code.\n" \
              "Provided partial code:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    prompt += "Code review:\n"
    prompt += review
    prompt += "\nPlease generate the revised code."
    return prompt
def generate_new_prompt4(old_without_minus, review):
    '''
    P1 + Concise Requirements.
    '''
    prompt = ""
    prompt += "code snippet:\n"
    prompt += "```\n{}\n```\n".format(old_without_minus)
    prompt += "code review:\n"
    prompt += review
    prompt += "\nPlease generate the revised code according to the review. " \
              "Please ensure that the revised code follows the original code format" \
              " and comments, unless it is explicitly required by the review."
    return prompt
def generate_new_prompt5(old_without_minus, review):
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












def get_chatgptapi_response(prompt,temperature=1.0):
    client = OpenAI(
        api_key = "" # your api key
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # 确保使用正确的模型名称
        messages=[
            {"role": "system", "content": "You are an experienced reviewer reviewing code changes."},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature
    )
    # print(response)
    answer = response.choices[0].message.content
    print("answer: ",answer)
    return ""

def main(id):
    record = get_db_info(id)
    if record:
        record_id, repo, commit_hash, pr_id, review ,path, code_diff, context = record
        prompt = generate_review_prompt(code_diff, context)
        get_chatgptapi_response(prompt)

if __name__ == "__main__":
    main(10231)