import os

os.chdir(r'D:\project-AI\werewolf_v5\backend')

def fix_double_encoding(content):
    try:
        fixed = content.encode('latin-1').decode('utf-8')
        return fixed
    except:
        pass
    try:
        fixed = content.encode('latin-1').decode('gbk')
        return fixed
    except:
        pass
    return content

for filename in ['main.py', 'schemas.py', 'models.py']:
    print(f'处理 {filename}...')
    
    content = None
    for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']:
        try:
            with open(filename, 'r', encoding=enc) as f:
                content = f.read()
            print(f'  用 {enc} 读取成功')
            break
        except:
            continue
    
    if content:
        fixed = fix_double_encoding(content)
        
        with open(filename, 'w', encoding='utf-8', newline='\n') as f:
            f.write(fixed)
        print(f'  保存成功')
        
        lines = fixed.split('\n')[:5]
        print(f'  前5行:')
        for i, line in enumerate(lines):
            print(f'    {i+1}: {line[:60]}')
    else:
        print(f'  无法读取文件')
    print()
