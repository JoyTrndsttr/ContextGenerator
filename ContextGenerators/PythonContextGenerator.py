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
        self.context = {}
        self.precise_context = {}

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
        self.node_list = []
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
                    if child.type in ["def", "class", "identifier"]:
                        self.node_list.append(child)
            else:
                self.find_node_by_range(child)

    def find_definition(self, cursor):
        def count_indent(s):#计算字符串的缩进的空格数
            return len(s) - len(s.lstrip(' '))
        
        script = jedi.Script(self.source_code, path=self.file_path)
        definitions = script.goto(cursor[0]+1, cursor[1]+1,follow_imports=True)
        if not definitions: print(f'no definition found in {self.file_path} at ({cursor[0]+1},{cursor[1]+1})')
        for definition in definitions:
            print(f"definition: {definition.name} in {definition.module_path._str}")
            if not definition.module_path or not definition.full_name: continue
            # if definition.module_path._str.find(self.repo_name) == -1: continue  //是否查找内置函数的定义
            name = definition.name
            path = definition.full_name if definition.full_name else definition.module_name
            type = definition.type
            text = []
            try:
                with open(definition.module_path._str, 'r', encoding='utf-8') as f:
                    file_source_code = f.read().split('\n')
                    start = definition.line - 1
                    end  = start + 1
                    while end<len(file_source_code)-2 and not (count_indent(file_source_code[start])==count_indent(file_source_code[end]) and not file_source_code[end]==''):
                        end += 1
                    for i in range(start, end):
                        text.append(file_source_code[i])
            except FileNotFoundError:
                print(f"FileNotFoundError: {definition.module_path_str}")
            return {'name': name, 'path': path, 'type': type, 'text': '\n'.join(text)}    
        return None

    def getContext(self):
        current_function = self.super_function
        name_list = []
        for index, node in enumerate(self.node_list):
            if node.type in ["def", "class"]:
                current_function = self.node_list[index+1].text
            elif node.type == "identifier":
                definition = self.find_definition(node.start_point)
                if definition:
                    if definition['name'] not in name_list:
                        self.context.setdefault(current_function,[]).append(definition)
                        self.precise_context.setdefault(current_function,[]).append({'name': definition['name'], 'type': definition['type']})
                        name_list.append(definition['name'])
        print(self.precise_context)
        return self.context

        


        


        
