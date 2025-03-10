#getContextGenerator.py
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
import re
import traceback
# from ContextGenerators import PythonContextGenerators
# from ContextGenerators import JavaContextGenerators
# from ContextGenerators.PythonContextGenerator import PythonContextGenerator
from PythonContextGenerator import PythonContextGenerator

# 设置日志记录
logging.basicConfig(filename='debug.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

class LanguageContextGenerator:
    def __init__(self, id):
        #初始化变量
        self.id = id
        self.repo_base_path = "/mnt/ssd2/wangke/CR_data/repo/"
        self.output_path = "/mnt/ssd2/wangke/CR_data/dataset/cacr_python_all.json"
        self.language_parsers = {
            '.c': self.load_language(Language(tsc.language())),
            '.cpp': self.load_language(Language(tscpp.language())),
            '.cs': self.load_language(Language(tscs.language())),
            '.go': self.load_language(Language(tsgo.language())),
            '.java': self.load_language(Language(tsjava.language())),
            '.js': self.load_language(Language(tsjs.language())),
            '.py': self.load_language(Language(tspython.language())),
            '.rb': self.load_language(Language(tsruby.language())),
        }

        #从json文件中获取记录
        with open(self.output_path, 'r', encoding='utf-8') as file: 
            records = json.load(file)
            for record in records:
                if record['_id'] == id:
                    self.record = record
        if not self.record: return None
        self.record_id, self.repo_name, self.paths, self.code_diffs, self.old, self.comment = self.record['_id'], self.record['repo'], self.record['path'], self.record['code_diff'] , self.record['old'], self.record['comment']
        self.code_diffs = json.loads(self.code_diffs)
        self.repo_path = os.path.join(self.repo_base_path, self.repo_name.split('/')[1])

        #匹配old和code_diff,获取old在源代码中的位置
        match,start_index,end_index = False, -1, -1
        self.file_path = None
        for path,code_diff in self.code_diffs.items():
            match, start_index,end_index = self.compare_old_and_diff(self.old, code_diff)
            self.file_path = os.path.join(self.repo_path, path)
            if match: break
        if not match or not os.path.exists(self.file_path): return None
        self.code_diff = code_diff

        #获取评论在old code中指向的位置
        if self.comment:
            diff_hunk_lines = self.comment["diff_hunk"].split('\n')
            try:
                start = int(re.search(r'(\d+)', diff_hunk_lines[0]).group(1))
                if self.comment["original_start_line"]:
                    self.comment["review_hunk_start_line"] = diff_hunk_lines[self.comment["original_start_line"]-start+1][1:] #加1是因为第一行是code_diff_hunk的prefix
                index = len(diff_hunk_lines)-1 # 指向review_position_line
                # if self.comment["original_position"] > len(diff_hunk_lines):
                #     if self.comment["original_line"]: index = self.comment["original_line"]-start+1
                #     else: raise Exception("original_position is out of range and original_line is not provided")
                # else: index = self.comment["original_position"]
                for i in range(index, -1, -1):
                    line = diff_hunk_lines[i][1:]
                    if line:
                        self.comment["review_position_line"] = line
                        break
            except Exception as e:
                print(f"Error finding start position of comment in old code: {e}")
                traceback.print_exc()

        #获取文件后缀并加载对应的语言解析器和上下文生成器
        self.file_extension = os.path.splitext(self.file_path)[1]
        if self.file_extension not in ['.py', '.java']: return None
        self.parser = self.language_parsers[self.file_extension]
        self.tree,self.source_code = self.parse_file(self.file_path, self.parser)
        self.context_generator = None
        if self.file_extension == '.py':
            self.context_generator = PythonContextGenerator(self.parser, self.tree.root_node, self.source_code, self.file_path, self.code_diff, self.repo_name, (start_index, end_index))

    def compare_old_and_diff(self, old, code_diff):
        code_diff_lines = code_diff.split('\n')
        old_lines = old.split('\n')
        old_lines = [line for line in old_lines if line]
        positions = []
        for old_line in old_lines:
            flag = False
            if old_line in code_diff_lines:
                positions.append(code_diff_lines.index(old_line))
                flag = True
            else:
                for index, line in enumerate(code_diff_lines):
                    position = line.find(old_line)
                    if position != -1:
                        positions.append(index)
                        flag = True
                        break
            if not flag:
                return False, -1, -1
        return True, positions[0], positions[-1]
    
    def load_language(self, language): # 加载语言包
        parser = Parser()
        parser.language = language
        return parser

    def parse_file(self, file_path, parser):# 解析代码文件
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        tree = parser.parse(source_code.encode('utf8'))
        return tree, source_code

# def store_context_to_jsonfile(record_id, context):
#     with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python.json', 'r', encoding='utf-8') as file:
#         records = json.load(file)
#         for record in records:
#             if record['_id'] == record_id:
#                 record['context'] = context
#                 break
#         with open('/mnt/ssd2/wangke/CR_data/dataset/cacr_python.json', 'w', encoding='utf-8') as file:
#             json.dump(records, file, indent=4)

# 主函数
def main(id):
    languageContextGenerator = LanguageContextGenerator(id)
    if not languageContextGenerator: return None
    contextGenetor = languageContextGenerator.context_generator
    context = contextGenetor.getContext()
    print(context)

if __name__ == "__main__":
    main(-4071)