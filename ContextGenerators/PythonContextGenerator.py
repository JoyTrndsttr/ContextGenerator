import re
import jedi
import json

class PythonContextGenerator:
    def __init__(self, node, source_code, file_path, path, code_diff, repo_name, code_range):
        self.tree = node
        self.source_code = source_code
        self.file_path = file_path
        self.path = path
        self.code_diff = code_diff
        self.repo_name = repo_name
        self.start_index, self.end_index = code_range

        #根据code_diff和code_range找到old在source_code中从哪一行开始到哪一行结束
        code_diff_lines = self.code_diff.split('\n')
        code_diff_prefix = code_diff_lines[self.start_index-1]  ##sample '@@ -274,6 +274,7 @@ def get(self):'
        start = int(re.search(r'(\d+)', code_diff_prefix).group(1)) - 1
        end = start + (self.end_index - self.start_index)
        self.start_index, self.end_index = start, end
        
        #找到old最近的上层定义
        source_code_lines = self.source_code.split('\n')
        super_function = "default_function"
        line = start
        while line > 0 and (source_code_lines[line].startswith(' ') or source_code_lines[line].startswith('')):
            if source_code_lines[line].strip().startswith('def ') or source_code_lines[line].strip().startswith('class '):
                super_function = source_code_lines[line].split('def ')[1].split('(')[0]
                break
            line -= 1
        self.super_function = super_function

        self.testSet = set()
        self.testCount = 0
        #查找所有start_point的行号在self.start_index与self.end_index之间的特定类型node节点
        self.identifier_node_list = []
        self.def_node_list = []
        self.find_node_by_range(self.tree)

    def find_node_by_range(self, node):
        if not node: return None
        for child in node.children:
            if child.start_point[0] > self.end_index or child.end_point[0] < self.start_index:
                continue
            self.testCount += 1
            if len(child.children) == 0:
                self.testSet.add(child.type)
                if child.start_point[0] in range(self.start_index, self.end_index):
                    if child.type == "identifier":
                        self.identifier_node_list.append(child)
                    elif child.type in ["def", "class"]:
                        self.def_node_list.append(child)
            else:
                self.find_node_by_range(child)

    def getContext(self):
        
        context = []
        current_function = self.super_function


        


        
