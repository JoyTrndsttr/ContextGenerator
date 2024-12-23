import re
import jedi
import json

class PythonContextGenerator:
    def __init__(self, parser, node, source_code, file_path, code_diff, repo_name, code_range):
        self.repo_path = "/mnt/ssd2/wangke/CR_data/repo/repo_name"
        self.parser = parser
        self.tree = node
        self.source_code = source_code
        self.file_path = file_path
        self.code_diff = code_diff
        self.repo_name = repo_name
        self.start_index, self.end_index = code_range
        self.context = {}
        # self.precise_context = {}

        #根据code_diff和code_range找到old在source_code中从哪一行开始到哪一行结束
        code_diff_lines = self.code_diff.split('\n')
        for i in reversed(range(0,self.start_index)):
            code_diff_prefix = code_diff_lines[i]  ##sample '@@ -274,6 +274,7 @@ def get(self):'
            if code_diff_prefix.startswith('@@'): break
        start = int(re.search(r'(\d+)', code_diff_prefix).group(1))
        end = start + (self.end_index - self.start_index)
        self.start_index, self.end_index = start, end
        
        #找到old最近的上层定义
        source_code_lines = self.source_code.split('\n')
        super_function = "default_function"
        line = start
        while line > 0 and (source_code_lines[line].startswith(' ') or source_code_lines[line].startswith('')):
            if source_code_lines[line].strip().startswith('def '):
                super_function = source_code_lines[line].split('def ')[1].split('(')[0]
                break
            elif source_code_lines[line].strip().startswith('class '):
                super_function = source_code_lines[line].split('class ')[1].split('(')[0]
                break
            line -= 1
        self.super_function = super_function

        self.testSet = set()
        self.testCount = 0
        #查找所有start_point的行号在self.start_index与self.end_index之间的特定类型node节点
        self.node_list = []
        self.name_list = []
        self.find_node_by_range(self.tree)
        self.definitions = []
        self.pricise_definitions = []
        self.calls = [] #存储调用关系，元组形式(调用函数名，被调用函数名)

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

    def get_definition_text_info(self, definition):
        def count_indent(s):#计算字符串的缩进的空格数
            return len(s) - len(s.lstrip(' '))
        
        text, start, end = [], -1, -1
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
            return None, None, None
        return '\n'.join(text), start, end

    def find_definition(self, cursor):
        script = jedi.Script(self.source_code, path=self.file_path)
        definitions = script.goto(cursor[0]+1, cursor[1]+1,follow_imports=True)
        if not definitions: print(f'No definition found in {self.file_path} at ({cursor[0]+1},{cursor[1]+1})')
        for definition in definitions:
            if not definition.module_path or not definition.full_name: continue
            print(f"Find definition: {definition.name} in {definition.module_path._str}")
            # if definition.module_path._str.find(self.repo_name) == -1: continue  //是否查找内置函数的定义
            name = definition.name
            path = definition.full_name if definition.full_name else definition.module_name
            type = definition.type
            text, start, end = self.get_definition_text_info(definition)
            return {'name': name, 'path': path, 'type': type, 'text': text} , definition   
        return None, None

    def getContext(self):
        current_function = self.super_function
        for index, node in enumerate(self.node_list):
            if node.type in ["def", "class"]:
                current_function = self.node_list[index+1].text.decode('utf-8')
            elif node.type == "identifier":
                definition, _definition = self.find_definition(node.start_point)
                if definition:
                    if definition['name'] not in self.name_list:
                        definition['caller'] = current_function
                        # self.context.setdefault(current_function,[]).append(definition) #仅包含四个元素的definition对象
                        self.pricise_definitions.append(definition) #包含五个元素的definition对象
                        # self.precise_context.setdefault(current_function,[]).append({'name': definition['name'], 'type': definition['type']})
                        self.definitions.append(_definition) #完整版的definition对象
                        self.name_list.append(definition['name']) #用于去重
                        self.calls.append((current_function, definition['name'])) #存储调用关系
        # print(self.context)
        return self.pricise_definitions
    
    def updateSource(self, name):
        #根据name找到对应的definition,更新self的参数以获取进一步的context
        for definition in self.definitions:
            if definition.name == name:
                self.file_path = definition.module_path._str
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.source_code = f.read()
                    self.tree = self.parser.parse(self.source_code.encode('utf8')).root_node
                text, start, end = self.get_definition_text_info(definition)
                # start, end = start+1, end+1

                #找到old最近的上层定义
                source_code_lines = self.source_code.split('\n')
                super_function = "default_function"
                line = start
                while line > 0 and (source_code_lines[line].startswith(' ') or source_code_lines[line].startswith('')):
                    if source_code_lines[line].strip().startswith('def '):
                        super_function = source_code_lines[line].split('def ')[1].split('(')[0]
                        break
                    elif source_code_lines[line].strip().startswith('class '):
                        super_function = source_code_lines[line].split('class ')[1].split('(')[0]
                        break
                    line -= 1
                self.super_function = super_function

                self.node_list = []
                self.start_index, self.end_index = start+1, end+1
                self.find_node_by_range(self.tree)
                return True

        


        


        
