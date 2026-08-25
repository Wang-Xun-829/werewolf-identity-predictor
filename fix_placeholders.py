# 读取文件
with open('logic_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 处理每一行
new_lines = []
for line in lines:
    # 如果行中包含 %s 且是SQL查询字符串，改成f-string并用 {ph()} 替换
    if '%s' in line and ('SELECT' in line or 'INSERT' in line or 'UPDATE' in line or 'DELETE' in line or 'query_all' in line or 'query_one' in line or 'execute_write' in line):
        # 把 %s 替换成 {ph()}
        line = line.replace('%s', '{ph()}')
        # 把字符串改成f-string（在第一个引号前加f）
        # 处理双引号
        if '"' in line and 'f"' not in line:
            # 找到第一个双引号的位置
            idx = line.find('"')
            if idx > 0:
                line = line[:idx] + 'f' + line[idx:]
        # 处理单引号
        elif "'" in line and "f'" not in line:
            idx = line.find("'")
            if idx > 0:
                line = line[:idx] + 'f' + line[idx:]
    new_lines.append(line)

# 写回文件
with open('logic_engine.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('替换完成！')

# 验证
with open('logic_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()
print('剩余 %s 数量:', content.count('%s'))
print('{ph()} 数量:', content.count('{ph()}'))
