import re
import jedi
import json

#在项目中寻找模块的定义并输出上下文
def find_definition(source_code, file_path, cursor, repo_name):
    def count_indent(s):#计算字符串的缩进的空格数
        return len(s) - len(s.lstrip(' '))

    script = jedi.Script(source_code, path=file_path)
    context = []
    definition = {}
    definitions = script.goto(cursor[0]+1, cursor[1]+1,follow_imports=True)
    # definitions = script.goto(132, 23)
    
    if not definitions:
        print(f'no definition found in {file_path} at ({cursor[0]+1},{cursor[1]+1})')
        return '', '', ''

    for definition in definitions:
        full_name = definition.full_name
        if not definition.module_path or definition.module_path._str.find(repo_name) == -1: continue
        if not full_name : continue
        #检查是不是全包含call_name_parts
        valid = True
        # for part in call_name_parts:
        #     if not part == 'self' and full_name.find(part) == -1:
        #         valid = False
        if valid :
            module_path = definition.full_name
            _type       = definition.type
            if not module_path:
                module_path = definition.module_name
            
            try:
                with open(definition.module_path._str, 'r', encoding='utf-8') as f:
                    file_source_code = f.read().split('\n')
                    start = definition.line - 1
                    end  = start + 1
                    while end<len(file_source_code)-2 and not (count_indent(file_source_code[start])==count_indent(file_source_code[end]) and not file_source_code[end]==''):
                        end += 1
                    for i in range(start, end):
                        context.append(file_source_code[i])
            except FileNotFoundError:
                print(f"FileNotFoundError: {definition.module_path_str}")

            return module_path, _type, '\n'.join(context)
    return '','',''
    # if definitions:
    #     definition  = definitions[0] #取第一个定义
    #     #处理param 'self'
    #     if definitions[0].name == 'self':
    #         self_definitions = script.goto(cursor[0]+1, cursor[1]+5)
    #         if not self_definitions:
    #             print(f'no self_definition found in {file_path} at ({definitions[0].line+1},{definitions[0].column+1})')
    #             return '', '', ''
    #         definition = self_definitions[0]
    #     #避免找到的是当前文件中的import定义
    #     elif definitions[0].module_path._str == file_path :
    #         def_definitions = script.goto(definitions[0].line,definitions[0].column)
    #         if not def_definitions:
    #             print(f'no def_definition found in {file_path} at ({definitions[0].line+1},{definitions[0].column+1})')
    #             return '', '', ''
    #         definition = def_definitions[0]

#在AST中查找特定类型的第一个位置
def find_definition_node(node, name, node_type):#node_type包括function_definition,class_definition,call......
    if not node: return None
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

#从文件中找到代码的起始位置
def find_code_start_index_in_file(file_path, code):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_source_code = f.read().splitlines()

        # 处理待匹配的 code，移除每行的首字符
        code_lines = [line[1:] for line in code.split('\n') if len(line) > 1]

        # 若 code_lines 为空，直接返回 -1
        if not code_lines:
            return -1

        code_length = len(code_lines)
        file_length = len(file_source_code)

        # 逐行尝试匹配子序列
        for i in range(file_length - code_length + 1):
            if file_source_code[i:i+code_length] == code_lines:
                return i

        # 若未找到匹配，返回 -1
        return -1

    except FileNotFoundError:
        print(f"FileNotFoundError: {file_path}")
        return -1

#找到最近的上层定义
def find_recent_def(file_path, line):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_source_code = f.read().split('\n')
            line -= 1
            while line > 0 and (file_source_code[line].startswith(' ') or file_source_code[line].startswith('')):
                if file_source_code[line].startswith('def ') or file_source_code[line].startswith('    def '):
                # if file_source_code[line].startswith('def') or file_source_code[line].startswith('class'):
                    return file_source_code[line].split('def ')[1].split('(')[0]
                line -= 1
    except FileNotFoundError:
        print(f"FileNotFoundError: {file_path}")
    return 'default_def'

#计算所有调用点的游标
def calculate_cursor_positions(start_cursor, call_text):
    current_line, current_column = start_cursor
    cursor_list = []
    last_index = 0
    for match in re.finditer(r'\.?(\w+)', call_text):
        part_name = match.group(1)
        part_start = match.start(1)
        newline_count = call_text[last_index:part_start].count('\n')
        if newline_count > 0:
            last_newline = call_text.rfind('\n', last_index, part_start)
            current_line += newline_count
            current_column = part_start - (last_newline + 1)
        else:
            current_column += (part_start - last_index)
        cursor_list.append((part_name, (current_line, current_column)))
        last_index = part_start
    return cursor_list

def find_node_by_cursor(tree, start_cursor, end_cursor):
    if not tree: return None
    for child in tree.children:
        if child.start_point == start_cursor and child.end_point == end_cursor:
            return child
        else :
            return find_node_by_cursor(child, start_cursor, end_cursor)
    return None

def getContext(tree, source_code, file_path, path, code_diff, repo_name, old, cursors):
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
    _context_ = {} #只包含函数信息的_context

    path = re.sub('/','.',path.split('.')[0])
    class_name = 'undefined'

    find_code_start_index_in_file(file_path, old)

    #对出现代码改动的地方，寻找涉及的函数或者import信息，@@行提到的函数或类也算进去
    current_line  = -1
    current_super_class_or_def = 'default_def'
    for line in code_diff.split('\n'):
        if line.startswith('@@'):
            if not str.isdigit(line.split('-')[1].split(',')[0]): #处理如@@ -1 +0,0 @@的情况
                current_line = int(line.split('-')[1].split(' ')[0])
            else: current_line = int(line.split('-')[1].split(',')[0])
            current_super_class_or_def = find_recent_def(file_path, current_line)
            if not current_super_class_or_def == 'default_def':
                context["Functions"].add(f"{current_super_class_or_def}")
            #'@@'一行中出现的函数或类有很多情况和代码变更是不相关的，只是恰好为代码变更函数的上一个函数
            # hunk_function = line.split('def ')
            # if(len(hunk_function) > 1):
            #     func_name = line.split('(')[0].split(' ')[-1]
            #     if current_super_class_or_def == func_name :
            #         context["Functions"].add(f"{func_name}")
            #     else :
            #         context["Functions"].add(f"{current_super_class_or_def}.{func_name}")
            # hunk_function = line.split('class ')
            # if(len(hunk_function) > 1):
            #     class_name = line.split('(')[0].split(' ')[-1]
            #     context["Classes"].add(f"{class_name}")

        line_content = line
        if line.startswith('+') or line.startswith('-'):
            line_content = line[1:] #去符号

        if line.startswith('+'):
            continue #用于代码细化任务
        
        if line_content.startswith(' def '):
            func_name = line_content.split('(')[0].split(' ')[-1]
            context["Functions"].add(f"{func_name}")
            current_super_class_or_def = func_name
        elif line_content.startswith('     def '):
            func_name = line_content.split('(')[0].split(' ')[-1]
            context["Functions"].add(f"{current_super_class_or_def}.{func_name}")
        elif line_content.startswith(' class '):
            class_name = line_content.split('(')[0].split(' ')[-1]
            context["Classes"].add(f"{class_name}")
            current_super_class_or_def = class_name
        elif line_content.startswith(' import '):
            imports = line_content.split('import ')[1].split(',')
            for imp in imports:
                context["Imports"].add(imp.strip())
        elif line_content.startswith(' from '):
            parts = line_content.split(' ')
            module = parts[1]
            sub_modules = parts[3].split(',')
            for sub in sub_modules:
                context["Imports"].add(f"{module}.{sub.strip()}")

    #TODO: 加上script.get_references信息
    for function_name in context['Functions']:
        call_context_list = []
        call_name_list = set()
        #寻找这个函数调用了哪些函数
        parts = function_name.split('.')
        if len(parts) == 1 :
            func_node = find_definition_node(tree, function_name, 'function_definition')
        else :
            super_class_or_def,func_name = parts[0],parts[1]
            super_class_or_def_node = find_definition_node(tree, super_class_or_def, 'function_definition')
            if not super_class_or_def_node :
                super_class_or_def_node = find_definition_node(tree, super_class_or_def, 'class_definition')
            func_node = find_definition_node(super_class_or_def_node, func_name, 'function_definition')
        
        if func_node:
            call_node_list = find_call_node(func_node)
            #将这些函数信息存入context中
            for call_node in call_node_list:
                call_name_text = call_node.child_by_field_name('function').text.decode('utf-8')
                call_list = calculate_cursor_positions(call_node.start_point, call_name_text)
                for call in call_list:
                    call_context = {}
                    call_name,cursor = call
                    try:
                        module_path, _type, text = find_definition(source_code, file_path, cursor, repo_name)
                    except Exception as e:
                        print(f"Error find definition {call_name} in {file_path}:{e}")
                        continue
                    if not text:
                        continue
                    call_context['Call_name'] = call_name
                    call_context['Call_path'] = module_path
                    call_context['Call_text'] = text
                    call_context['Call_type'] = _type
                    if call_name not in call_name_list and not _type == "module":#module包含了整个文件内容，内容量太大
                        call_context_list.append(call_context)
                        call_name_list.add(call_name)
        _context['Functions'][f'{function_name}'] = call_context_list
        _context_[f'{function_name}'] = call_context_list

    # for function_name in context['Classes']:
    #     call_context_list = []
    #     call_name_list = set()
    #     call_context = {}
    #     #寻找这个类中有哪些函数调用
    #     func_node = find_definition_node(tree, class_name, 'class_definition')
    #     if func_node:
    #         call_node_list = find_call_node(func_node)
    #         #将这些函数信息存入context中
    #         for call_node in call_node_list:
    #             call_name = re.compile(r'\(.*?\)').sub('',call_node.child_by_field_name('function').text.decode('utf-8'))#去除括号以及参数
    #             cursor    = call_node.start_point
    #             module_path, _type, text = find_definition(source_code, file_path, cursor, repo_name)
    #             if not text:
    #                 continue
    #             call_context['Call_name'] = call_name
    #             call_context['Call_path'] = module_path
    #             call_context['Call_text'] = text
    #             call_context['Call_type'] = _type
    #             if call_name not in call_name_list:
    #                 call_context_list.append(call_context)
    #                 call_name_list.add(call_name)
    #         _context['Classes'][f'{function_name}'] = call_context_list

    for _import in context['Imports']:
        _context['Imports'].append(_import)
    return _context_