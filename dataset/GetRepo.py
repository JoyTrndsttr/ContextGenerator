import json
import psycopg2
from psycopg2 import sql

# 数据库连接配置
db_config = {
    'dbname': 'HCGGraph',
    'user': 'user',
    'password': '123456',
    'host': 'localhost',
    'port': '5432'
}

def store_jsonfile_to_postgres(file_path):
    repo_data = {}
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            json_entry = json.loads(line)
            _id = json_entry.get('_id')
            old = json_entry.get('old', '')
            new = json_entry.get('new', '')
            review = json_entry.get('review', '')
            language = json_entry.get('language', '')
            repo = json_entry.get('repo', '')
            review_url = json_entry.get('review_url', '')
            commit_url = json_entry.get('commit_url', '')
            type = json_entry.get('type', '')
            gpt_answer = json_entry.get('gpt_answer', '')
            gpt_code = json_entry.get('gpt_code', '')
            model_code = json_entry.get('model_code', '')
            model_em = json_entry.get('model_em', 0)
            model_em_trim = json_entry.get('model_em_trim', 0)
            model_bleu = json_entry.get('model_bleu', 0.0)
            model_bleu_trim = json_entry.get('model_bleu_trim', 0.0)
            gpt_em = json_entry.get('gpt_em', 0)
            gpt_em_trim = json_entry.get('gpt_em_trim', 0)
            gpt_bleu = json_entry.get('gpt_bleu', 0.0)
            gpt_bleu_trim = json_entry.get('gpt_bleu_trim', 0.0)

            if language == "py":
                conn = psycopg2.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO cacr_py (
                        _id, old, new, review, language, repo, review_url, commit_url, 
                        type, gpt_answer, gpt_code, model_code, model_em, model_em_trim, 
                        model_bleu, model_bleu_trim, gpt_em, gpt_em_trim, gpt_bleu, gpt_bleu_trim
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    );
                """, (
                    _id, old, new, review, language, repo, review_url, commit_url,
                    type, gpt_answer, gpt_code, model_code, model_em, model_em_trim,
                    model_bleu, model_bleu_trim, gpt_em, gpt_em_trim, gpt_bleu, gpt_bleu_trim
                ))
                conn.commit()
                cursor.close()
                conn.close()
            
    return repo_data

def store_to_json(file_path, output_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        with open(output_path, 'w', encoding='utf-8') as output_file:
            output_file.write("[\n    ")
            first_record = True
            for line in file:
                record = json.loads(line)
                if record["language"] == "java":
                    record["code_diff"] = ""
                    record["context"] = ""
                    record["path"] = ""
                    record["llama_code"] = ""
                    record["llama_em"] = 0
                    record["llama_em_trim"] = 0
                    record["llama_bleu"] = 0.0
                    record["llama_bleu_trim"] = 0.0
                    print(f"processing {record['_id']}")
                    if not first_record:
                        output_file.write(",\n    ")
                    output_file.write(json.dumps(record))
                    first_record = False
            output_file.write("\n]")
            
def main():
    # Working directory is set to a specific path
    # files = ['codereview.jsonl', 'codereview_new.jsonl']
    files = ['/mnt/ssd2/wangke/CR_data/dataset/codereview.jsonl', '/mnt/ssd2/wangke/CR_data/dataset/codereview_new.jsonl']
    store_to_json(files[1], '/mnt/ssd2/wangke/CR_data/dataset/cacr_java2.json')
    # all_repos = {}
    # for file_path in files:
        # repos = store_jsonfile_to_postgres(file_path)
        # all_repos.update(repos)

if __name__ == "__main__":
    main()
