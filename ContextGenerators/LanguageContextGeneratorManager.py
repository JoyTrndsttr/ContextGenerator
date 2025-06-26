import os
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
from ContextGenerators.PythonContextGenerator import PythonContextGenerator
from ContextGenerators.JavaContextGenerator import JavaContextGenerator
from ContextGenerators.JsContextGenerator import JsContextGenerator

class LanguageContextGenerator:
    def __init__(self, record):
        #初始化变量
        self.record = record
        self.repo_base_path = "/data/DataLACP/wangke/recorebench/repo/repo/"
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
        self.record_id, self.repo_name, self.code_diff, self.file_path, self.old, self.comment = self.record['_id'], self.record['repo'], self.record['diff_hunk'], self.record['path'], self.record['old'], self.record['comment']
        self.abs_file_path = os.path.join(self.repo_base_path, self.repo_name.split('/')[1], self.file_path)

        #截取RevisionDiffHunk的行号
        try:
            revision_diff_hunk_lines = self.code_diff.split('\n')[0]
            original_code_start, orginal_code_scope, revised_code_start, revised_code_scope = re.findall(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', revision_diff_hunk_lines)[0]
            self.ostart, self.oend = int(original_code_start), int(original_code_start) + int(orginal_code_scope)
            self.rstart, self.rend = int(revised_code_start), int(revised_code_start) + int(revised_code_scope)
        except:
            raise Exception("Invalid code_diff format")

        #获取文件后缀并加载对应的语言解析器和上下文生成器
        self.file_extension = os.path.splitext(self.file_path)[1]
        if self.file_extension not in ['.py', '.java', ".js"]: 
            raise Exception("Unsupported file type")
        self.language = self.file_extension
        self.context_generator = self.get_context_generator()
        
    def get_context_generator(self, type = "original"):
        start = self.ostart
        if type == "original":
            end = self.oend
        elif type == "revised":#由于只Apply了RevisionDiffHunk，所以不能简单按照rstart和rend来计算
            plus_count = len([line for line in self.code_diff.split('\n') if line.startswith('+')])
            minus_count = len([line for line in self.code_diff.split('\n') if line.startswith('-')])
            end = self.oend + plus_count - minus_count
        language = self.language
        if language == '.py':
            self.parser = self.language_parsers[self.file_extension]
            self.tree, self.source_code = self.parse_file(self.file_path, self.parser)
            return PythonContextGenerator(self.parser, self.tree.root_node, self.source_code, self.file_path, self.code_diff, self.repo_name, (1, start - end))
        elif language == '.java':
            self.parser = self.language_parsers[self.file_extension]
            self.tree, self.source_code = self.parse_file(self.abs_file_path, self.parser)
            return JavaContextGenerator(self.parser, self.tree.root_node, self.source_code, self.file_path, self.repo_name, (start, end))
        elif language == '.js':
            self.parser = self.language_parsers[self.file_extension]
            self.tree, self.source_code = self.parse_file(self.abs_file_path, self.parser)
            return JsContextGenerator(self.parser, self.tree.root_node, self.source_code, self.file_path, self.repo_name, (start, end))
        else:
            return None
    
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