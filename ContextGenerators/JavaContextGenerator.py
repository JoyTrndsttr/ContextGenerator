import os
import subprocess
import pexpect
import re
import json
class JavaContextGenerator:
    def __init__(self, parser, node, source_code, file_path, repo_name, code_range):
        self.parser = parser
        self.tree = node
        self.source_code = source_code
        self.start_index, self.end_index = code_range
        self.rel_file_path = file_path
        self.repo = repo_name.split('/')[1]
        self.base_repo_dir = f"/data/DataLACP/wangke/recorebench/repo/repo/{self.repo}"
        self.abs_file_path = f"{self.base_repo_dir}/{self.rel_file_path}"
        self.workspace = f"/data/DataLACP/wangke/recorebench/workspace/{self.repo}"
        if not os.path.exists(self.workspace): os.makedirs(self.workspace)
        self.tool_path = "/home/wangke/bin/joern/joern-cli/javasrc2cpg"
        self.workspace_path = f"{self.workspace}/cpg.bin.zip"
        self.tmp_output_path = f"{self.workspace}/tmp.json"
        self.all_types = ["method", "typeDecl", "block", "call", "identifier", "local", "methodParameterIn", "methodParameterOut", "methodReturn", "file", "member", "annotation", "modifier", "return", "jumpTarget", "controlStructure", "unknown", "type", "namespaceBlock", "methodRef", "typeRef", "fieldIdentifier", "tag", "comment", "methodInst", "typeArgument", "typeParameter", "cfgNode"]
        self.supported_types = ["method", "typeDecl", "call", "identifier", "local", "methodParameterIn", "member", "annotation", "fieldIdentifier"]
        self.processed_instructions = []

        #采用Treesitter寻找node, 并获取variable的定义
        self.node_list = []
        self.find_node_by_range(self.tree)
        self.node_names = list(set([node.text.decode() for node in self.node_list]))

    def search_context(self):
        #采用Joern进一步寻找上下文
        self.initialize_joern()
        self.context = {
            "method_call": {},
            "annotation": {},
            "variable": {},
            "field_access": {},
            "type_identifier": {}
        }
        self.find_node_context()
        self.NIDS = [] # New Identifier Definition Strict
        for _, defs in self.context.items():
            for key, value in defs.items():
                if value and value not in ['<unknown>', 'Unresolved', '<empty>']:
                    self.NIDS.append(key)
        # 此方法暂时废弃
        # self.identifiers_names, self.identifiers_definition_strict, self.identifiers = self.get_definitions_by_range(code_range[0], code_range[1])

    def initialize_joern(self):
        # Generate CPG
        print(f"Generating CPG")
        command = [
            self.tool_path,
            self.base_repo_dir,
            "--output", self.workspace_path,
            "--enable-file-content"
        ]
        subprocess.run(command, check=True)
        self.processed_instructions.append(' '.join(command))

        # Load CPG
        print(f"Loading CPG")
        try:
            self.child = pexpect.spawn("joern", timeout=60)
        except Exception as e:
            print(f"Error: {e}")
            raise ValueError("Timeout when starting joern")
        self.child.expect("joern>")
        self.child.sendline(f'importCpg("{self.workspace_path}")')
        self.processed_instructions.append(f'importCpg("{self.workspace_path}")')
        self.child.expect("joern>")
        print(self.child.before.decode())

    def find_node_by_range(self, node):
        if not node: return None
        for child in node.children:
            if child.start_point[0] + 1 > self.end_index or child.end_point[0] + 1 < self.start_index:
                continue
            if len(child.children) == 0:
                if self.start_index <= child.start_point[0] + 1 <= self.end_index:
                    if child.type in ["identifier", "type_identifier"]:
                        self.node_list.append(child)
            else:
                self.find_node_by_range(child)
    
    def find_identifier_def_and_use(self, identifier_name):
        # 在Treesitter构建的AST中寻找identifier在OrignalCode前的定义和使用
        appeared_lines = set()
        def search_node(node):
            if not node: return
            # 只有OrignalCode之前的上下文被考虑在内
            if node.start_point[0] + 1 >= self.start_index: return
            if node.text.decode() == identifier_name:
                appeared_lines.add(node.start_point[0] + 1)
            for child in node.children:
                search_node(child)
        search_node(self.tree)
        lines = list(appeared_lines)
        if len(lines) == 0:
            return []
        identifier_context = []
        with open(f"{self.base_repo_dir}/{self.rel_file_path}", "r") as f:
            source_code = f.readlines()
            for line_number, line in enumerate(source_code):
                if line_number + 1 in lines:
                    identifier_context.append(f"line {line_number + 1}: {line}")
        return identifier_context

    def find_cross_file_code(self, type, representation):
        # 在当前文件中使用Joern寻找(caller, callee)中callee的ast节点，判断其第一个children是否为caller
        OUTPUT_FORMAT = f".toJsonPretty #> \"{self.tmp_output_path}\""
        def get_call_info(callee):
            return f"cpg.call.where(_.file.nameExact(\"{self.rel_file_path}\")).filter(call => call.name == \"{callee}\").map(call => (call, call.astChildren.head.code)).l{OUTPUT_FORMAT}"
        def get_method_code(method_full_name):
            return f"cpg.method.filter(_.fullName == \"{method_full_name}\").headOption{OUTPUT_FORMAT}"
        def get_field_access_info(field_access_text):
            return f"cpg.call.where(_.file.nameExact(\"{self.rel_file_path}\")).filter(call => call.code == \"{field_access_text}\").l{OUTPUT_FORMAT}"
        def get_type_decl_info(type_full_name):
            return f"cpg.typeDecl.fullName(\"{type_full_name}\").l{OUTPUT_FORMAT}"
        def get_type_from_local(type_name):
            #由于Joern对泛型分析有问题，这里只匹配以type_name开头的local
            return f"cpg.local.where(_.file.nameExact(\"{self.rel_file_path}\")).code(\"{type_name}.*\").l{OUTPUT_FORMAT}"
        def get_annotation_info(full_name):
            return f"cpg.annotation.where(_.file.nameExact(\"{self.rel_file_path}\")).name(\"{full_name}\").l{OUTPUT_FORMAT}"
        
        if type == "call":
            caller, callee = representation
            callee_node = None
            call_infos = self.get_command_output(get_call_info(callee))
            for call_info in call_infos:
                _callee_node, _caller = call_info["_1"], call_info["_2"]
                if caller == _caller:
                    callee_node = _callee_node
                    break
            if not callee_node: return None
            method_full_name = callee_node.get("methodFullName", "Unresolved")
            if method_full_name == "Unresolved": return None
            definition = self.get_command_output(get_method_code(method_full_name))
            if definition: return definition[0].get("filename", None)
            return None
        elif type == "field_access":
            field_access_text = representation
            field_access_infos = self.get_command_output(get_field_access_info(field_access_text))
            if not field_access_infos: return None
            field_access_info = field_access_infos[0]
            type_full_name = field_access_info.get("typeFullName", "Unresolved")
            if type_full_name == "Unresolved": return None
            definition = self.get_command_output(get_type_decl_info(type_full_name))
            if definition: return definition[0].get("filename", None)
            return None
        elif type == "type_identifier":
            type_name = representation
            locals = self.get_command_output(get_type_from_local(type_name))
            if not locals: return None
            type_full_name = locals[0].get("typeFullName", "Unresolved")
            if type_full_name == "Unresolved": return None
            definition = self.get_command_output(get_type_decl_info(type_full_name))
            if definition: return definition[0].get("filename", None)
            return None
        elif type == "annotation":
            annotation_name = representation
            annotation_infos = self.get_command_output(get_annotation_info(annotation_name))
            if not annotation_infos: return None
            annotation_info = annotation_infos[0]
            full_name = annotation_info.get("fullName", "Unresolved")
            if full_name == "Unresolved": return None
            definition = self.get_command_output(get_type_decl_info(full_name))
            if definition: return definition[0].get("filename", None)
            return None
        else:
            print(f"Warning: Unconsidered type {type}")
            return None
    
    def find_node_context(self):
        context = {
            "method_call": {},
            "annotation": {},
            "variable": {},
            "field_access": {},
            "type_identifier": {}
        }
        for node in self.node_list:
            identifier_name = node.text.decode()
            if node.type in ["type_identifier"]: # 类
                context["type_identifier"][identifier_name] = self.find_cross_file_code("type_identifier", identifier_name)
                continue
            parent_node = node.parent
            if parent_node.type in ["method_invocation"]:
                # 函数调用需要重点考虑
                children = parent_node.children
                method_call = []
                if len(children) == 2: #对应 [identifier, argument_list]
                    assert children[0].type == "identifier"
                    assert children[1].type == "argument_list"
                    method_call = ("this", children[0].text.decode())
                elif len(children) == 4: #对应 [method_invocation | identifier, '.', identifier, argument_list]
                    assert children[0].type in ["method_invocation", "identifier", "field_access"]
                    assert children[1].type == "."
                    assert children[2].type == "identifier"
                    assert children[3].type == "argument_list"
                    if children[0].type == "identifier":
                        method_call = (children[0].text.decode(), children[2].text.decode())
                    elif children[0].type == "method_invocation":
                        # 对于由method_invocation调用的call，考虑到链式调用的返回值路径敏感，且Joern分析不出来，暂时不考虑
                        pass
                if not method_call:
                    context["method_call"][identifier_name] = "Unresolved"
                else:
                    context["method_call"][identifier_name] = self.find_cross_file_code("call", method_call)
            elif parent_node.type in ["annotation", "marker_annotation"]:
                # annotation类型为通用注解，可能带参数； marker_annotation类型为标记注解，不带参数
                context["annotation"][identifier_name] = self.find_cross_file_code("annotation", identifier_name)
            elif parent_node.type in ["variable_declarator", "formal_parameter", "constructor_declaration", "class_declaration", "method_declaration", "resource", 
                                      "package_declaration", "interface_declaration"]:
                # variable_declarator包括局部变量和成员变量声明，形参，构造函数，成员方法声明的定义都会出现在OrignalCode范围内，不需要额外上下文
                # resource包括try-with-resources语句中的资源声明, 类似于variable_declarator
                pass
            elif parent_node.type in ["field_access"]:
                # field_access和method_invocation类似，需要重点考虑
                # treesitter的field_access的text内容和joern的field_access的call节点的code一致
                context["field_access"][identifier_name] = self.find_cross_file_code("field_access", parent_node.text.decode())
            # else:
            #     print(f"Warning: Unconsidered node type {parent_node.type}")
            # elif parent_node.type in ["assignment_expression", "argument_list", "switch_label", "binary_expression", "lambda_expression", "catch_formal_parameter",
            #                           "enhanced_for_statement", "inferred_parameters", "instanceof_expression", "update_expression"]:
            #     # 这些情况为variable的local use， 其数据流可能不位于OrignalCode范围内，需要重点考虑
            else:
                # 把其他所有情况都当做Variable分析
                context["variable"][identifier_name] = self.find_identifier_def_and_use(identifier_name)
        self.context = context
        return context

    def find_method_definition(self):
        # 在当前文件中使用Joern寻找(caller, callee)中callee的ast节点，判断其第一个children是否为caller
        OUTPUT_FORMAT = f".toJsonPretty #> \"{self.tmp_output_path}\""
        def get_call_info(callee):
            return f"cpg.call.where(_.file.nameExact(\"{self.rel_file_path}\")).filter(call => call.name == \"{callee}\").map(call => (call, call.astChildren.head.code)).l{OUTPUT_FORMAT}"
        def get_method_code(method_full_name):
            return f"cpg.method.filter(_.fullName == \"{method_full_name}\").headOption{OUTPUT_FORMAT}"
        
        method_definition = []
        for caller, callee in self.method_call:
            callee_node = None
            call_infos = self.get_command_output(get_call_info(callee))

            for call_info in call_infos:
                _callee_node, _caller = call_info["_1"], call_info["_2"]
                if caller == _caller:
                    callee_node = _callee_node
                    break
            if callee_node:
                method_definition.append((caller, callee, callee_node.get("methodFullName", "Unresolved")))
        method_definition = list(set(method_definition))
        for caller, callee, method_full_name in method_definition:
            if method_full_name == "Unresolved": continue
            definition = self.get_command_output(get_method_code(method_full_name))
            if definition: code = definition[0].get("code", None)
            self.method_definition.append((caller, callee, method_full_name, code))
        self.method_definition = list(set(self.method_definition))
        return self.method_definition
    
    def get_command_output(self, command):
        try:
            self.child.sendline(command)
            self.processed_instructions.append(command)
            self.child.expect("joern>")
            with open(self.tmp_output_path, 'r') as f:
                output = json.load(f)
            open(self.tmp_output_path, 'w').close()
            return output
        except Exception as e:
            print(f"Error: {e}")
            return None

    def get_definitions_by_range(self, line_start, line_end):
        #根据行号来获取identifier的定义，由于joern会预解析文档改变行号，此方法暂时废弃
        OUTPUT_FORMAT = f".toJsonPretty #> \"{self.tmp_output_path}\""
        def template(type):
            return f"cpg.{type}.where(_.file.nameExact(\"{self.rel_file_path}\")).filter({type} => {type}.lineNumber.get >= {line_start} && {type}.lineNumber.get <= {line_end}){OUTPUT_FORMAT}"
        def get_identifier_definition(identifier_name):
            return f"cpg.local.where(_.file.nameExact(\"{self.rel_file_path}\")).filter(local => local.name == \"{identifier_name}\").headOption{OUTPUT_FORMAT}"
        def get_method_definition(method_full_name):
            return f"cpg.method.filter(_.fullName == \"{method_full_name}\").headOption{OUTPUT_FORMAT}"
        def get_annotation_definition(full_name):
            return f"cpg.annotation.filter(_.fullName == \"{full_name}\").headOption{OUTPUT_FORMAT}"
        def get_file_source_code(start, end):
            with open(f"{self.base_repo_dir}/{self.rel_file_path}", 'r') as f:
                source_code = f.readlines()[start:end]
            return "".join(source_code)
        
        identifiers = {}
        for type in self.supported_types:
            identifiers[type] = self.get_command_output(template(type))
        filtered_identifiers = {}
        identifiers_names = []
        for key, value in identifiers.items():
            if not value: continue
            for identifier in value:
                if identifier['_label'] == 'Label': 
                    #需要处理，TextureAtlasSprite sprite，既要有TextureAtlasSprite，又要有sprite
                    pass
                if identifier['_label'] == 'FIELD_IDENTIFIER': identifier['name'] = identifier['code']
                if identifier.get('name') != 'this' and re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', identifier.get('name') or ''):
                    if identifier.get('name') == "SaSecureUtil":
                        pass
                    identifiers_names.append(identifier['name'])
                    if filtered_identifiers.get(key, None):
                        filtered_identifiers[key].append(identifier)
                    else:
                        filtered_identifiers[key] = [identifier]
        unique_identifiers_names = list(set(identifiers_names))

        identifiers_definition_strict = []
        for key, value in filtered_identifiers.items():
            for identifier in value:
                if key == "identifier": # identifier 的定义是同文件下的局部变量，定义在identifier之前，而且我们不需要考虑OriginalCode范围内的定义
                    identifier_definition = self.get_command_output(get_identifier_definition(identifier['name']))
                    if identifier_definition: identifier_definition = identifier_definition[0]
                    else: continue
                    line_number = identifier_definition.get("lineNumber", None) # line_number = 0 不是我们要考虑的场景
                    if line_number and line_number < line_start:
                        identifier["definition"] = get_file_source_code(line_number-1, line_number)
                elif key == "call":
                    method_definition = self.get_command_output(get_method_definition(identifier['methodFullName']))
                    if method_definition: method_definition = method_definition[0]
                    else: continue
                    line_number = method_definition.get("lineNumber", None)
                    line_number_end = method_definition.get("lineNumberEnd", None)
                    if line_number and line_number_end:
                        identifier["definition"] = get_file_source_code(line_number-1, line_number_end)
                elif key == "annotation":
                    annotation_definition = self.get_command_output(get_annotation_definition(identifier['fullName']))
                    if annotation_definition: annotation_definition = annotation_definition[0]
                    else: continue
                    line_number = annotation_definition.get("lineNumber", None)
                    line_number_end = annotation_definition.get("lineNumberEnd", None)
                    if line_number and line_number_end:
                        identifier["definition"] = get_file_source_code(line_number-1, line_number_end)
                if identifier.get("definition", None):
                    identifiers_definition_strict.append(identifier.get('name'))
        unique_identifiers_definition_strict = list(set(identifiers_definition_strict))

        return unique_identifiers_names, unique_identifiers_definition_strict, filtered_identifiers
    
def main():
    javacontextGenerator = JavaContextGenerator("/data/DataLACP/wangke/recorebench/repo/repo/kafka-ui/kafka-ui-e2e-checks/src/main/java/com/provectus/kafka/ui/pages/Pages.java", "AAA/kafka-ui", (0, 52))

if __name__ == '__main__':
    main()