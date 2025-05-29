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
            "--output", self.workspace_path
        ]
        subprocess.run(command, check=True)

        # Load CPG
        print(f"Loading CPG")
        self.child = pexpect.spawn("joern")
        self.child.expect("joern>")
        self.child.sendline(f'importCpg("{self.workspace_path}")')
        self.child.expect("joern>")
        print(self.child.before.decode())

        #根据文件路径获取文件id
        try:
            self.rel_file_path = file_path.split(f"{self.repo}/", 1)[1]
            result_json = self.get_command_output(f"cpg.file.nameExact(\"{self.rel_file_path}\").id.toJsonPretty #> \"{self.tmp_output_path}\"")
            self.file_id = result_json[0]
            print(f"file_id: {self.file_id}")
        except:
            raise ValueError("Cannot find repo_name in file_path")
        print(f"rel_file_path: {self.rel_file_path}")
        
        self.identifiers_names, self.identifiers = self.get_definitions_by_range(self.file_id, code_range[0], code_range[1])

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

    def get_definitions_by_range(self, file_id, line_start, line_end):
        def template(type):
            return f"cpg.{type}.where(_.file.id({file_id}L)).filter({type} => {type}.lineNumber.get >= {line_start} && {type}.lineNumber.get <= {line_end}).toJsonPretty #> \"{self.tmp_output_path}\""
        
        identifiers = {}
        for type in self.supported_types:
            identifiers[type] = self.get_command_output(template(type))
        filtered_identifiers = {}
        unique_identifiers_names = []
        for key, value in identifiers.items():
            for identifier in value:
                if identifier['_label'] == 'FIELD_IDENTIFIER': identifier['name'] = identifier['code']
                if identifier.get('name') != 'this' and identifier.get('name').find('<') == -1:
                    if filtered_identifiers.get(key, None):
                        filtered_identifiers[key].append(identifier)
                        unique_identifiers_names.append(identifier['name'])
                    else:
                        filtered_identifiers[key] = [identifier]
        unique_identifiers_names = list(set(unique_identifiers_names))
        return unique_identifiers_names, filtered_identifiers

def main():
    javacontextGenerator = JavaContextGenerator("/data/DataLACP/wangke/recorebench/repo/repo/kafka-ui/kafka-ui-e2e-checks/src/main/java/com/provectus/kafka/ui/pages/Pages.java", "AAA/kafka-ui", (0, 52))

if __name__ == '__main__':
    main()


    

        