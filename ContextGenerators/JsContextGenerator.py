import os
import subprocess
import pexpect
import re
import json
class JsContextGenerator:
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
        self.tool_path = "/home/wangke/bin/joern/joern-cli/jssrc2cpg.sh"
        self.workspace_path = f"{self.workspace}/cpg.bin.zip"
        self.tmp_output_path = f"{self.workspace}/tmp.json"
        self.all_types = ["method", "typeDecl", "block", "call", "identifier", "local", "methodParameterIn", "methodParameterOut", "methodReturn", "file", "member", "annotation", "modifier", "return", "jumpTarget", "controlStructure", "unknown", "type", "namespaceBlock", "methodRef", "typeRef", "fieldIdentifier", "tag", "comment", "methodInst", "typeArgument", "typeParameter", "cfgNode"]
        self.supported_types = ["method", "typeDecl", "call", "identifier", "local", "methodParameterIn", "member", "annotation", "fieldIdentifier", "typeIdentifier"]
        self.processed_instructions = []

        #采用Treesitter寻找node, 并获取variable的定义
        self.node_list = []
        self.find_node_by_range(self.tree)
        self.node_names = list(set([node.text.decode() for node in self.node_list]))

    def search_context(self):
        #采用Joern进一步寻找上下文
        self.initialize_joern()
        _, unique_identifiers_definition_strict, _ = self.get_definitions_by_range()
        unique_identifiers_definition_strict = list(set(unique_identifiers_definition_strict))
        self.NIDS = unique_identifiers_definition_strict # New Identifier Definition Strict
        #此方法暂时废弃
        # for _, defs in self.context.items():
        #     for key, value in defs.items():
        #         if value and value not in ['<unknown>', 'Unresolved', '<empty>']:
        #             self.NIDS.append(key)

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
            self.child = pexpect.spawn("joern", timeout=120)
        except Exception as e:
            print(f"Error: {e}")
            raise ValueError("Timeout when starting joern")
        self.child.expect("joern>")
        self.child.sendline(f'importCpg("{self.workspace_path}")')
        self.processed_instructions.append(f'importCpg("{self.workspace_path}")')
        self.child.expect("joern>")
        print(self.child.before.decode())
    
    def terminate_joern(self):
        self.child.close(force=True)

    def find_node_by_range(self, node):
        if not node: return None
        for child in node.children:
            if child.start_point[0] + 1 > self.end_index or child.end_point[0] + 1 < self.start_index:
                continue
            if len(child.children) == 0:
                if self.start_index <= child.start_point[0] + 1 <= self.end_index:
                    if child.type in ["identifier", "property_identifier"]:
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

    def get_source_code_and_processed_code(self):
        # 获取文件处理前和处理后代码，仅做调试用
        OUTPUT_FORMAT = f".toJsonPretty #> \"{self.tmp_output_path}\""
        def get_file():
            return f"cpg.file.nameExact(\"{self.rel_file_path}\").headOption{OUTPUT_FORMAT}"
        return self.source_code, self.get_command_output(get_file())
    
    def find_cross_file_code(self, type, representation):
        # 在当前文件中使用Joern寻找(caller, callee)中callee的ast节点，判断其第一个children是否为caller
        OUTPUT_FORMAT = f".toJsonPretty #> \"{self.tmp_output_path}\""
        def get_call_info(callee):
            return f"cpg.call.where(_.file.nameExact(\"{self.rel_file_path}\")).filter(call => call.name == \"{callee}\").map(call => (call, call.astChildren.head.code)).l{OUTPUT_FORMAT}"
        def get_method_code(method_full_name):
            return f"cpg.method.filter(_.fullName == \"{method_full_name}\").headOption{OUTPUT_FORMAT}"
        def get_member_expression_info(member_expression_text):
            return f"cpg.call.where(_.file.nameExact(\"{self.rel_file_path}\")).filter(call => call.code == \"{member_expression_text}\").l{OUTPUT_FORMAT}"
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
        elif type == "member_expression":
            member_expression_text = representation
            member_expression_infos = self.get_command_output(get_member_expression_info(member_expression_text))
            if not member_expression_infos: return None
            member_expression_info = member_expression_infos[0]
            type_full_name = member_expression_info.get("typeFullName", "Unresolved")
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
            "member_expression": {}
        }
        for node in self.node_list:
            identifier_name = node.text.decode()
            if node.type in ["property_identifier"]: # 成员变量，有可能是匿名类的成员变量
                # member_expression和method_invocation类似，需要重点考虑
                # treesitter的member_expression的text内容和joern的member_expression的call节点的code一致
                context["member_expression"][identifier_name] = self.find_cross_file_code("member_expression", parent_node.text.decode())
            parent_node = node.parent
            if parent_node.type in ["member_expression"]:
                # 函数调用需要重点考虑
                # js的call_expression格式：<member_expression>, <arguments> ; <identifier>, <arguments>
                # member_expression格式：<identifier>.<property_identifier> | <call_expression>.<property_identifier>
                children = parent_node.children
                assert len(children) == 3
                method_call = (children[0].text.decode(), children[2].text.decode())
                context["method_call"][identifier_name] = self.find_cross_file_code("call", method_call)
            elif parent_node.type in ["annotation", "marker_annotation"]:
                # annotation类型为通用注解，可能带参数； marker_annotation类型为标记注解，不带参数
                context["annotation"][identifier_name] = self.find_cross_file_code("annotation", identifier_name)
            elif parent_node.type in ["variable_declarator", "lexical_declaration", "formal_parameters"]:
                # variable_declarator包括局部变量和成员变量声明，形参，构造函数，成员方法声明的定义都会出现在OrignalCode范围内，不需要额外上下文
                # resource包括try-with-resources语句中的资源声明, 类似于variable_declarator
                pass
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

    def get_definitions_by_range(self):
        #joern对JavaScript的解析不会改变行号
        OUTPUT_FORMAT = f".toJsonPretty #> \"{self.tmp_output_path}\""
        OUTER_SCOPE = f".repeat(_.astParent)(_.until(_.isMethod))"
        #模板：cpg.local.where(_.file.nameExact("src/modules/Search/Search.js")).nameExact("debug").filter(local => local.closureBindingId.isEmpty).map(local => (local, cpg.local.id(local.id).repeat(_.astParent)(_.until(_.isMethod)).cast[Method].fullName.headOption)).l
        def template(type):
            return f"cpg.{type}.where(_.file.nameExact(\"{self.rel_file_path}\")).filter({type} => {type}.lineNumber.get >= {line_start} && {type}.lineNumber.get <= {line_end}){OUTPUT_FORMAT}"
        def get_identifier_refsTo(identifier_name):
            return f"cpg.identifier.where(_.file.nameExact(\"{self.rel_file_path}\")).filter(identifier => identifier.name == \"{identifier_name}\").refsTo.l{OUTPUT_FORMAT}"
        def get_closureBinding_in(identifier_name, closureBindingId): #获取上一层作用域
            return f"def typeFullName = cpg.closureBinding.closureBindingIdExact({closureBindingId}).in.headOption{OUTPUT_FORMAT}" + \
                   f"cpg.typeDecl.filter(typeDecl => typeDecl.fullName == typeFullName).astChildren.code(\"{identifier_name}\"){OUTPUT_FORMAT}"
        def get_identifier_local_def(identifier_name):# local不能绑定有闭包id，否则是闭包中声明的local
            return f"cpg.local.where(_.file.nameExact(\"{self.rel_file_path}\")).nameExact(\"{identifier_name}\").filter(local => local.closureBindingId.isEmpty){OUTPUT_FORMAT}"
        def get_identifier_assignment_def(identifier_name):
            return f"cpg.call.where(_.file.nameExact(\"{self.rel_file_path}\")).name(\"<operator>.assignment\").filter(call => call.astChildren.cast[Identifier].code.head == \"{identifier_name}\").l{OUTPUT_FORMAT}"
        def get_identifiers(identifier_name):
            return f"cpg.identifier.where(_.file.nameExact(\"{self.rel_file_path}\")).filter(identifier => identifier.name == \"{identifier_name}\").l{OUTPUT_FORMAT}"
        def get_method_definition(method_full_name):
            return f"cpg.method.filter(_.fullName == \"{method_full_name}\").headOption{OUTPUT_FORMAT}"
        def get_annotation_definition(full_name):
            return f"cpg.annotation.filter(_.fullName == \"{full_name}\").headOption{OUTPUT_FORMAT}"
        def get_data_flow(identifier_name, source_line_number, sink_line_number):
            return f"def source = cpg.identifier.where(_.file.nameExact(\"{self.rel_file_path}\")).filter(identifier => identifier.name == \"{identifier_name}\").lineNumber({source_line_number}).l;" + \
                   f"def sink   = cpg.identifier.where(_.file.nameExact(\"{self.rel_file_path}\")).filter(identifier => identifier.name == \"{identifier_name}\").lineNumber({sink_line_number}).l;" + \
                   f"sink.reachableByFlows(source){OUTPUT_FORMAT}"
        def get_field_identifier_definition(field_identifier_name):
            return f"def typeFullName = cpg.fieldIdentifier.where(_.file.nameExact(\"{self.rel_file_path}\")).filter(fieldIdentifier => fieldIdentifier.name == \"{field_identifier_name}\").astSiblings.headOption;" + \
                   f"cpg.typeDecl.filter(typeDecl => typeDecl.fullName == typeFullName).astChildren.code(\"{field_identifier_name}\"){OUTPUT_FORMAT}"
        def get_file_source_code(rel_path, start, end=None):
            try:
                #这种拼接方式保证了只有在repo路径下才能找到代码定义
                start = start -1
                with open(f"{self.base_repo_dir}/{rel_path}", 'r') as f:
                    if end: source_code = f.readlines()[start:end-1+1]
                    else: source_code = f.readlines()[start]
                return "".join(source_code)
            except:
                return None
        def get_file_source_code_by_offset(rel_path, start, end):
            try:
                #这种拼接方式保证了只有在repo路径下才能找到代码定义
                with open(f"{self.base_repo_dir}/{rel_path}", 'r') as f:
                    content = f.read()
                return content[start:end]
            except:
                return None
            
        line_start, line_end = self.start_index, self.end_index
        identifiers = {}
        for type in self.supported_types:
            identifiers[type] = self.get_command_output(template(type))
        filtered_identifiers = {}
        identifiers_names = []
        for key, value in identifiers.items():
            if not value: continue
            for identifier in value:
                if identifier['_label'] == 'FIELD_IDENTIFIER': identifier['name'] = identifier['code']
                if not (identifier.get('name') != 'this' and re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', identifier.get('name') or '')): continue
                if not identifier.get('name') in self.node_names: continue
                identifiers_names.append(identifier['name'])
                if filtered_identifiers.get(key, None):
                    filtered_identifiers[key].append(identifier)
                else:
                    filtered_identifiers[key] = [identifier]
        unique_identifiers_names = list(set(identifiers_names))

        identifiers_definition_strict = []
        for key, value in filtered_identifiers.items():
            for identifier in value:
                if key == "_identifier": # identifier 的定义是同文件下的局部变量，定义在identifier之前，而且我们不需要考虑OriginalCode范围内的定义
                    # 对于js来说，导入的模块也会作为一个局部变量; 
                    # 对于js来说，闭包中使用作用域外的定义，会在闭包中声明一个local，干扰数据流分析
                    # 因此，此方法暂时弃用
                    sink_line_number = identifier.get('lineNumber', None)
                    if not sink_line_number: continue
                    identifiers = self.get_command_output(get_identifiers(identifier['name']))
                    #获取identifiers中lineNumber属性不超过self.start_index的最大lineNumber的identifier
                    last_identifer = max(
                        (id for id in identifiers if id.get('lineNumber') is not None and id["lineNumber"] < self.start_index), 
                        key=lambda id: id.get('lineNumber', 0),
                        default=None)
                    if last_identifer: source_line_number = last_identifer.get('lineNumber')
                    else: continue
                    data_flow_of_identifier = self.get_command_output(get_data_flow(identifier['name'], source_line_number, sink_line_number))
                    if data_flow_of_identifier:
                        identifier["definition"] = data_flow_of_identifier
                elif key == "identifier":
                    # 检查在OrignalCode之前是否有local定义和assignment定义
                    assignment_defs = self.get_command_output(get_identifier_assignment_def(identifier['name']))
                    local_defs = self.get_command_output(get_identifier_local_def(identifier['name']))
                    identifier_definition = []
                    for local_def in local_defs:
                        if local_def.get("lineNumber") >= self.start_index: continue
                        if local_def.get("offset", None) and local_def.get("offsetEnd", None):
                            identifier_definition.append(get_file_source_code_by_offset(self.rel_file_path, local_def["offset"], local_def["offsetEnd"]))
                        else:
                            identifier_definition.append(get_file_source_code(self.rel_file_path, local_def["lineNumber"]))
                    # identifier_definition_lines = sorted(list(set([
                    #     identifier_def.get("lineNumber") for identifier_def in local_defs if identifier_def.get("lineNumber") < self.start_index
                    # ])))
                    # identifier_definition = [get_file_source_code(self.rel_file_path, identifier_definition_line) for identifier_definition_line in identifier_definition_lines]
                    identifier_definition.extend([
                        assignement_def.get("code") for assignement_def in assignment_defs if assignement_def.get("lineNumber") < self.start_index and assignement_def.get("code", None)
                    ])
                    identifier_definition = list(set([item for item in identifier_definition if item is not None]))
                    if identifier_definition:
                        identifier["definition"] = "\n".join(identifier_definition)
                elif key == "field_identifier": # joern对于js的成员变量不会存储其typeIdentifier，需要先找到其所在的typeDecl，然后再获取其定义
                    field_identifier_definition = self.get_command_output(get_field_identifier_definition(identifier['name']))
                    if field_identifier_definition: 
                        lineNumber = field_identifier_definition.get("lineNumber", None)
                        identifier["definition"] = get_file_source_code(filename, lineNumber)
                elif key == "call":
                    method_definition = self.get_command_output(get_method_definition(identifier['methodFullName']))
                    if method_definition: method_definition = method_definition[0]
                    else: continue
                    line_number = method_definition.get("lineNumber", None)
                    line_number_end = method_definition.get("lineNumberEnd", None)
                    filename = method_definition.get("filename", None)
                    if not filename: continue
                    if line_number and line_number_end:
                        definition_code = get_file_source_code(filename, line_number, line_number_end)
                        if definition_code: identifier["definition"] = definition_code
                elif key == "annotation":
                    annotation_definition = self.get_command_output(get_annotation_definition(identifier['fullName']))
                    if annotation_definition: annotation_definition = annotation_definition[0]
                    else: continue
                    line_number = annotation_definition.get("lineNumber", None)
                    line_number_end = annotation_definition.get("lineNumberEnd", None)
                    if not filename: continue
                    if line_number and line_number_end:
                        definition_code = get_file_source_code(filename, line_number-1, line_number_end)
                        if definition_code: identifier["definition"] = definition_code
                if identifier.get("definition", None):
                    identifiers_definition_strict.append(identifier.get('name'))
        unique_identifiers_definition_strict = list(set(identifiers_definition_strict))

        return unique_identifiers_names, unique_identifiers_definition_strict, filtered_identifiers
    
def main():
    javacontextGenerator = JsContextGenerator("/data/DataLACP/wangke/recorebench/repo/repo/kafka-ui/kafka-ui-e2e-checks/src/main/java/com/provectus/kafka/ui/pages/Pages.java", "AAA/kafka-ui", (0, 52))

if __name__ == '__main__':
    main()