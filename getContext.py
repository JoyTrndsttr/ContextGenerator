#TreeSitterGenerator.py
import os
import logging
import json
import psycopg2
from psycopg2 import sql
from tree_sitter import Language, Parser
import tree_sitter_c as tsc
import tree_sitter_cpp as tscpp
import tree_sitter_c_sharp as tscs
import tree_sitter_go as tsgo
import tree_sitter_java as tsjava
import tree_sitter_javascript as tsjs
import tree_sitter_python as tspython
import tree_sitter_ruby as tsruby
from ContextGenerators import PythonContextGenerators
# 设置日志记录
logging.basicConfig(filename='debug.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

# 数据库连接配置
db_config = {
    'dbname': 'HCGGraph',
    'user': 'user',
    'password': '123456',
    'host': 'localhost',
    'port': '5432'
}

# 初始化语言库路径
def init_languages():
    languages = {}
    languages['c'] = Language(tsc.language())
    languages['cpp'] = Language(tscpp.language())
    languages['c-sharp'] = Language(tscs.language())
    languages['go'] = Language(tsgo.language())
    languages['java'] = Language(tsjava.language())
    languages['javascript'] = Language(tsjs.language())
    languages['python'] = Language(tspython.language())
    languages['ruby'] = Language(tsruby.language())
    return languages

# 加载语言包
def load_language(language):
    parser = Parser()
    parser.language = language
    return parser

# 解析代码文件
def parse_file(file_path, parser):
    with open(file_path, 'r', encoding='utf-8') as f:
        source_code = f.read()
    tree = parser.parse(source_code.encode('utf8'))
    return tree, source_code

# 获取数据库中的信息
def get_db_info(id):
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT _id, repo, path, code_diff FROM cacr_py WHERE _id = %s", [id])
    record = cursor.fetchone()
    conn.close()
    return record

# 提取上下文信息
def extract_context(language_parsers, file_path, path, code_diff, repo_name):
    context = {}

    if not os.path.exists(file_path):
        return {}

    file_extension = os.path.splitext(file_path)[1]
    if file_extension not in ['.py']:
        return context
    
    logging.debug(f'processing:{file_path}')
    parser = language_parsers[file_extension]
    tree,source_code = parse_file(file_path, parser)

    if file_extension == '.py':
        context = PythonContextGenerators.getContext(tree.root_node, source_code, file_path, path, code_diff, repo_name)
    else:
        context = {
            "Imports": [],
            "Functions": []
        }

    return context

#存储context信息
def store_context(record_id, context):
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE cacr_py
        SET context = %s
        WHERE _id = %s;
    """, (context, record_id))
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Successfully store context of _id:{record_id}")

# 主函数
def main(id):
    # 设置项目路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_base_path = os.path.join(script_dir, 'dataset\\repo')
    output_path = os.path.join(script_dir, 'context.json')

    # 加载所有语言解析器
    languages = init_languages()

    # 创建语言解析器映射
    language_parsers = {
        '.c': load_language(languages['c']),
        '.cpp': load_language(languages['cpp']),
        '.cs': load_language(languages['c-sharp']),
        '.go': load_language(languages['go']),
        '.java': load_language(languages['java']),
        '.js': load_language(languages['javascript']),
        '.py': load_language(languages['python']),
        '.rb': load_language(languages['ruby']),
    }

    context = {}

    record = get_db_info(id)
    if record:
    # for record in records:
        record_id, repo_name, paths, code_diffs = record
        code_diffs = json.loads(code_diffs)
        repo_path = os.path.join(repo_base_path, repo_name.split('/')[1])

        for path,code_diff in code_diffs.items():
            file_path = os.path.join(repo_path, path.replace('/', '\\'))
            context[path] = extract_context(language_parsers, file_path, path, code_diff, repo_name.split('/')[1])
        store_context(record_id, json.dumps(context))

if __name__ == "__main__":
    main(6730)
