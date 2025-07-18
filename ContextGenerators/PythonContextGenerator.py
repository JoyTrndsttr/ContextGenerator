import re
import jedi
import json

class PythonContextGenerator:
    def __init__(self, parser, node, source_code, file_path, repo_name, code_range):
        self.parser = parser
        self.tree = node
        self.source_code = source_code
        self._source_code = source_code #用于存储原始代码
        self.rel_file_path = file_path
        self.repo = repo_name.split('/')[1]
        self.base_repo_dir = f"/data/DataLACP/wangke/recorebench/repo/repo/{self.repo}"
        self.file_path = f"{self.base_repo_dir}/{self.rel_file_path}"

        self.repo_name = repo_name
        self.context = {}
        self.start_index, self.end_index = code_range
        
        #找到old最近的上层定义
        source_code_lines = self.source_code.split('\n')
        super_function = "default_function"
        line = self.start_index - 1
        while line > 0 and (source_code_lines[line].startswith(' ') or source_code_lines[line].startswith('')):
            if source_code_lines[line].strip().startswith('def '):
                super_function = source_code_lines[line].split('def ')[1].split('(')[0]
                break
            elif source_code_lines[line].strip().startswith('class '):
                super_function = source_code_lines[line].split('class ')[1].split('(')[0]
                break
            line -= 1
        self.super_function = super_function

        #查找所有start_point的行号在self.start_index与self.end_index之间的特定类型node节点
        self.node_list = []
        self.name_list = []
        self.find_node_by_range(self.tree)
        self.definitions = []
        self.precise_definitions = []
        self.calls = [] #存储调用关系，元组形式(调用函数名，被调用函数名)
        self.file_paths = [] #检索范围
        self.file_paths.append(self.file_path)
        self.context = self.getContext()

    def get_repo_context(self):
        return [(definition['name'], definition['text']) for definition in self.context]
    
    def find_node_by_range(self, node):
        # tree node所存储的行的起始位置为0，而start和end记录的起始位置为1，同Github的Commit页面一致
        if not node: return None
        for child in node.children:
            if child.start_point[0] + 1 > self.end_index or child.end_point[0] + 1 < self.start_index:
                continue
            if len(child.children) == 0:
                if self.start_index <= child.start_point[0] + 1 <= self.end_index:
                    if child.type in ["identifier"]:
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
                if definition.type == "module":
                    return '\n'.join(file_source_code), 0, len(file_source_code)-1
                start = definition.line - 1
                end  = start + 1
                # while end<len(file_source_code)-2 and not (count_indent(file_source_code[start])==count_indent(file_source_code[end]) and not file_source_code[end]==''):
                while end<len(file_source_code)-2 and (count_indent(file_source_code[start]) < count_indent(file_source_code[end]) or file_source_code[end]==''):
                    end += 1
                for i in range(start, end):
                    text.append(file_source_code[i])
        except FileNotFoundError:
            print(f"FileNotFoundError: {definition.module_path._str}")
            return None, None, None
        return '\n'.join(text), start, end

    def find_definition(self, cursor):
        script = jedi.Script(self.source_code, path=self.file_path)
        definitions = script.goto(cursor[0]+1, cursor[1]+1,follow_imports=True)
        if not definitions: print(f'No definition found in {self.file_path} at ({cursor[0]+1},{cursor[1]+1})')
        for definition in definitions:
            if not definition.module_path or not definition.full_name: continue
            print(f"Find definition: {definition.name} in {definition.module_path._str}")
            # if definition.module_path._str.find(self.repo_name) == -1: continue  #是否查找内置函数的定义
            name = definition.name
            path = definition.full_name if definition.full_name else definition.module_name
            type = definition.type
            text, start, end = self.get_definition_text_info(definition)
            return {'name': name, 'path': path, 'type': type, 'text': text, 'caller': name} , definition   
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
                        self.precise_definitions.append(definition) #包含五个元素的definition对象
                        self.definitions.append(_definition) #完整版的definition对象
                        self.name_list.append(definition['name']) #用于去重
                        self.calls.append((current_function, definition['name'])) #存储调用关系
        # print(self.context)
        return self.precise_definitions
    
    def check_identifier_valid(self, identifier):
        # 此identifier的定义不在code block范围内，且不是内置函数，才算valid
        try:
            if identifier not in self.name_list: return False
            definition = next((definition for definition in self.definitions if definition.name == identifier), None)
            print(definition.module_path._str)
            if definition.module_path._str.find(self.repo_name.split('/')[-1]) == -1: return False #不查找内置函数的定义
            if definition.module_path._str == self.file_path and self.start_index <= definition.line - 1 <= self.end_index:
                return False
            return True
        except:
            return False

    def updateSource(self, name):
        #根据name找到对应的definition,更新self的参数以获取进一步的context
        for definition in self.definitions:
            if definition.name == name:
                self.file_path = definition.module_path._str
                if self.file_path not in self.file_paths:
                    self.file_paths.append(self.file_path)
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

    def search_definition(self, name):
        for path in self.file_paths:
            with open(path, 'r', encoding='utf-8') as f:
                source_code = f.read()
                # script = jedi.Script(source_code, path=path)
                self.source_code = source_code
                self.file_path = path
                positions = []
                #在整个source_code中寻找name出现的行号和列号
                for i, line in enumerate(source_code.split('\n')):
                    column = line.find(name)
                    if column != -1:
                        positions.append((i, column))
                #根据行号和列号找到definition
                for position in positions:
                    definition, _definition = self.find_definition(position)
                    if not definition: continue
                    else:
                        definition['name'] = name #有时候会有import A as B的情况
                        self.definitions.append(_definition)
                        if definition['name'] not in self.name_list:
                            self.precise_definitions.append(definition)
                        self.name_list.append(definition['name']) #用于去重
                        self.calls.append((definition['name'], definition['name'])) #存储调用关系
                        return self.precise_definitions
        return self.precise_definitions