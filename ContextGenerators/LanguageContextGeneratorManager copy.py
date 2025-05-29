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
from ContextGenerators.PythonContextGenerator import PythonContextGenerator

class LanguageContextGenerator:
    def __init__(self, record):
        #初始化变量
        self.record = record
        self.repo_base_path = "/data/DataLACP/wangke/recorebench/repo/repo/"
        # self.output_path = "/mnt/ssd2/wangke/CR_data/dataset/cacr_python_all.json"
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
        if not self.record: raise Exception("No record found")
        self.record_id, self.repo_name, self.paths, self.code_diffs, self.old, self.comment = self.record['_id'], self.record['repo'], self.record['path'], self.record['code_diff'] , self.record['old'], self.record['comment']
        self.code_diffs = json.loads(self.code_diffs)
        self.repo_path = os.path.join(self.repo_base_path, self.repo_name.split('/')[1])
        self.old = '\n'.join([line.strip() for line in self.old.split('\n') if line.strip()])

        #匹配old和code_diff,获取old在源代码中的位置
        match,start_index,end_index = False, -1, -1
        self.file_path = None
        patchs,patch = [], []
        for path,code_diff in self.code_diffs.items():
            for line in code_diff.split('\n'):
                if line.startswith('@@'):
                    if patch:
                        patchs.append(patch)
                    patch = [line]
                else:
                    patch.append(line)
            if patch: patchs.append(patch)
            for patch in patchs:
                patch = '\n'.join(patch)
                match, start_index, end_index = self.compare_old_and_diff(self.old, patch)
                self.file_path = os.path.join(self.repo_path, path)
                if match: break
            if match: break
        if not match or not os.path.exists(self.file_path): raise Exception("Cannot match old code in code diff")
        self.code_diff = patch

        #获取文件后缀并加载对应的语言解析器和上下文生成器
        self.file_extension = os.path.splitext(self.file_path)[1]
        if self.file_extension not in ['.py', '.java']: 
            raise Exception("Unsupported file type")
        self.parser = self.language_parsers[self.file_extension]
        self.tree,self.source_code = self.parse_file(self.file_path, self.parser)
        self.context_generator = None
        self.start_index, self.end_index = start_index, end_index
        if self.file_extension == '.py':
            self.context_generator = PythonContextGenerator(self.parser, self.tree.root_node, self.source_code, self.file_path, self.code_diff, self.repo_name, (start_index, end_index))
        elif self.file_extension == '.java':
            # self.context_generator = JavaContextGenerator()
            pass

    def get_context_generator_after_applying_diff(self):
        plus_count = len([line for line in self.code_diff.split('\n') if line.startswith('+')])
        minus_count = len([line for line in self.code_diff.split('\n') if line.startswith('-')])
        return PythonContextGenerator(self.parser, self.tree.root_node, self.source_code, self.file_path, self.code_diff, self.repo_name, (self.start_index, self.end_index + plus_count - minus_count))
    
    def compare_old_and_diff(self, old, code_diff):
        code_diff_lines = [line for line in code_diff.split('\n') if not line.startswith('+')]
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
        # return True, positions[0], positions[-1]
        return True, 1, len(code_diff_lines)-1
    
    def load_language(self, language): # 加载语言包
        parser = Parser()
        parser.language = language
        return parser

    def parse_file(self, file_path, parser):# 解析代码文件
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        tree = parser.parse(source_code.encode('utf8'))
        return tree, source_code

# 主函数
def main(id):
    pass
    # languageContextGenerator = LanguageContextGenerator(id)
    # if not languageContextGenerator: return None
    # contextGenetor = languageContextGenerator.context_generator
    # context = contextGenetor.getContext()
    # print(context)

if __name__ == "__main__":
    main(-4071)