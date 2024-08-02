import re
import jedi
import json

#在项目中寻找模块的定义并输出上下文
def find_definition(source_code, file_path, cursor, repo_name):
    script = jedi.Script(source_code, path=file_path)
    context = []
    definition = {}
    definitions = script.goto(cursor[0]+1, cursor[1]+1)
    # definitions = script.goto(132, 23)
    
    if not definitions:
        print(f'no definition found in {file_path} at ({cursor[0]+1},{cursor[1]+1})')
        return '', '', ''

    if definitions:
        definition  = definitions[0] #取第一个定义
        #避免找到的是当前文件中的import定义
        if definitions[0].module_path._str == file_path :
            def_definitions = script.goto(definitions[0].line,definitions[0].column)
            if not def_definitions:
                print(f'no def_definition found in {file_path} at ({definitions[0].line+1},{definitions[0].column+1})')
                return '', '', ''
            definition = def_definitions[0]
    
    if not definition or definition.module_path._str.find(repo_name) == -1:
        return '', '', ''
    
    module_path = definition.full_name
    _type       = definition.type
    if not module_path:
        module_path = definition.module_name
    
    try:
        with open(definition.module_path._str, 'r', encoding='utf-8') as f:
            file_source_code = f.read().split('\n')
            start = definition.line - 1
            end  = start + 1
            while end<len(file_source_code)-2 and not file_source_code[end].startswith('    def') and file_source_code[end].startswith(' ') or file_source_code[end]=='':
                end += 1
            for i in range(start, end):
                context.append(file_source_code[i])
    except FileNotFoundError:
        print(f"FileNotFoundError: {definition.module_path_str}")
    
    return module_path, _type, '\n'.join(context)

#在AST中查找特定类型的第一个位置
def find_definition_node(node, name, node_type):#node_type包括function_definition,class_definition,call......
    for child in node.children:
        if (child.type == node_type) and child.child_by_field_name('name').text.decode('utf-8') == name:
            return child
        # 递归查找子节点
        result = find_definition_node(child, name, node_type)
        if result:
            return result
    return None

#在AST中返回'call'类型的节点列表
def find_call_node(node):
    call_node_list = []
    for child in node.children:
        if (child.type == 'call'):
            call_node_list.append(child)
        for call_node in find_call_node(child):
            call_node_list.append(call_node)
    return call_node_list

def getContext(tree, source_code, file_path, path, code_diff, repo_name):
    context = {
        "Imports": set(),
        "Functions": set(),
        "Classes": set()
    }
    _context = { #包含更多信息的context
        "Imports": [],
        "Functions": {},
        "Classes": {}
    }

    path = re.sub('/','.',path.split('.')[0])
    class_name = 'undefined'
    for line in code_diff.split('\n'):
        if line.startswith('@@'):
            hunk_function = line.split('def ')
            if(len(hunk_function) > 1):
                func_name = line.split('(')[0].split(' ')[-1]
                context["Functions"].add(f"{func_name}")
            hunk_function = line.split('class ')
            if(len(hunk_function) > 1):
                class_name = line.split('(')[0].split(' ')[-1]
                context["Classes"].add(f"{class_name}")

        elif line.startswith('+') or line.startswith('-'):
            line_content = line[1:] #去符号
            if line_content.startswith('def '):
                func_name = line_content.split('(')[0].split(' ')[-1]
                context["Functions"].add(f"{func_name}")

            if line_content.startswith('class '):
                class_name = line_content.split('(')[0].split(' ')[-1]
                context["Classes"].add(f"{class_name}")
            
            elif line_content.startswith('import '):
                imports = line_content.split('import ')[1].split(',')
                for imp in imports:
                    context["Imports"].add(imp.strip())
            
            elif line_content.startswith('from '):
                parts = line_content.split(' ')
                module = parts[1]
                sub_modules = parts[3].split(',')
                for sub in sub_modules:
                    context["Imports"].add(f"{module}.{sub.strip()}")
            
            elif line_content.startswith('    def '):
                func_name = line_content.split('(')[0].split(' ')[-1]
                context["Functions"].add(f"{class_name}.{func_name}")

    for function_name in context['Functions']:
        call_context_list = []
        call_name_list = set()
        #寻找这个函数调用了哪些函数
        func_node = find_definition_node(tree, func_name, 'function_definition')
        if func_node:
            call_node_list = find_call_node(func_node)
            #将这些函数信息存入context中
            for call_node in call_node_list:
                call_context = {}
                call_name = re.compile(r'\(.*?\)').sub('',call_node.child_by_field_name('function').text.decode('utf-8'))#去除括号以及参数
                cursor    = call_node.start_point
                module_path, _type, text = find_definition(source_code, file_path, cursor, repo_name)
                if not text:
                    continue
                call_context['Call_name'] = call_name
                call_context['Call_path'] = module_path
                call_context['Call_text'] = text
                call_context['Call_type'] = _type
                if call_name not in call_name_list:
                    call_context_list.append(call_context)
                    call_name_list.add(call_name)
            _context['Functions'][f'{function_name}'] = call_context_list

    for function_name in context['Classes']:
        call_context_list = []
        call_name_list = set()
        call_context = {}
        #寻找这个类中有哪些函数调用
        func_node = find_definition_node(tree, class_name, 'class_definition')
        if func_node:
            call_node_list = find_call_node(func_node)
            #将这些函数信息存入context中
            for call_node in call_node_list:
                call_name = re.compile(r'\(.*?\)').sub('',call_node.child_by_field_name('function').text.decode('utf-8'))#去除括号以及参数
                cursor    = call_node.start_point
                module_path, _type, text = find_definition(source_code, file_path, cursor, repo_name)
                if not text:
                    continue
                call_context['Call_name'] = call_name
                call_context['Call_path'] = module_path
                call_context['Call_text'] = text
                call_context['Call_type'] = _type
                if call_name not in call_name_list:
                    call_context_list.append(call_context)
                    call_name_list.add(call_name)
            _context['Classes'][f'{function_name}'] = call_context_list

    for _import in context['Imports']:
        _context['Imports'].append(_import)
    return _context