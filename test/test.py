import re

def calculate_cursor_positions(start_cursor, call_text):
    current_line, current_column = start_cursor
    cursor_list = []
    last_index = 0

    # 逐个处理每个属性或方法
    for match in re.finditer(r'\.?(\w+)', call_text):
        part_name = match.group(1)
        part_start = match.start(1)

        # 跨行处理
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

# 示例调用
start_cursor = (10, 5)  # 假设从文件的第10行第5列开始
call_name_text = "self._config._get_retry_policy()._asdict"
cursor_list = calculate_cursor_positions(start_cursor, call_name_text)
print(cursor_list)

# 处理多行的复杂示例
call_name_text_multi = """bq_client.client.tables().delete(projectId=table_params[0], datasetId=table_params[1],
                                 tableId=table_params[2]).execute()"""
start_cursor_multi = (100, 0)  # 假设从文件的100行0列开始
cursor_list_multi = calculate_cursor_positions(start_cursor_multi, call_name_text_multi)
print(cursor_list_multi)