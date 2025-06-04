import os
import subprocess
import pexpect
import re
import json
class JavaContextGenerator:
    def __init__(self, file_path, repo_name, code_range):
        self.repo = repo_name.split('/')[1]
        self.base_repo_dir = f"/data/DataLACP/wangke/recorebench/repo/repo/{self.repo}"
        self.workspace = f"/data/DataLACP/wangke/recorebench/workspace/{self.repo}"
        if not os.path.exists(self.workspace): os.makedirs(self.workspace)
        self.tool_path = "/home/wangke/bin/joern/joern-cli/javasrc2cpg"
        self.workspace_path = f"{self.workspace}/cpg.bin.zip"
        self.tmp_output_path = f"{self.workspace}/tmp.json"
        self.all_types = ["method", "typeDecl", "block", "call", "identifier", "local", "methodParameterIn", "methodParameterOut", "methodReturn", "file", "member", "annotation", "modifier", "return", "jumpTarget", "controlStructure", "unknown", "type", "namespaceBlock", "methodRef", "typeRef", "fieldIdentifier", "tag", "comment", "methodInst", "typeArgument", "typeParameter", "cfgNode"]
        self.supported_types = ["method", "typeDecl", "call", "identifier", "local", "methodParameterIn", "member", "annotation", "fieldIdentifier"]
        
        # Generate CPG
        print(f"Generating CPG")
        command = [
            self.tool_path,
            self.base_repo_dir,
            "--output", self.workspace_path,
            "--enable-file-content"
        ]
        subprocess.run(command, check=True)

        # Load CPG
        print(f"Loading CPG")
        try:
            self.child = pexpect.spawn("joern", timeout=60)
        except Exception as e:
            print(f"Error: {e}")
            raise ValueError("Timeout when starting joern")
        self.child.expect("joern>")
        self.child.sendline(f'importCpg("{self.workspace_path}")')
        self.child.expect("joern>")
        print(self.child.before.decode())
        self.rel_file_path = file_path
        
        self.identifiers_names, self.identifiers_definition_strict, self.identifiers = self.get_definitions_by_range(code_range[0], code_range[1])

    def get_command_output(self, command):
        try:
            self.child.sendline(command)
            self.child.expect("joern>")
            with open(self.tmp_output_path, 'r') as f:
                output = json.load(f)
            open(self.tmp_output_path, 'w').close()
            return output
        except Exception as e:
            print(f"Error: {e}")
            return None

    def get_definitions_by_range(self, line_start, line_end):
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
                elif key == "method":
                    method_definition = self.get_command_output(get_method_definition(identifier['fullName']))
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
    
    # def get_context(self):
        

def main():
    javacontextGenerator = JavaContextGenerator("/data/DataLACP/wangke/recorebench/repo/repo/kafka-ui/kafka-ui-e2e-checks/src/main/java/com/provectus/kafka/ui/pages/Pages.java", "AAA/kafka-ui", (0, 52))

if __name__ == '__main__':
    main()