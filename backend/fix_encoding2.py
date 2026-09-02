import os

os.chdir(r'D:\project-AI\werewolf_v5\backend')

def try_fix_encoding(content):
    """尝试多种方式修复编码"""
    # 方式1: UTF-8 -> Latin-1 -> UTF-8
    try:
        fixed = content.encode('latin-1').decode('utf-8')
        if '狼人' in fixed or '身份' in fixed or '预测' in fixed:
            return fixed, 'UTF-8 -> Latin-1 -> UTF-8'
    except:
        pass
    
    # 方式2: UTF-8 -> Latin-1 -> GBK
    try:
        fixed = content.encode('latin-1').decode('gbk')
        if '狼人' in fixed or '身份' in fixed or '预测' in fixed:
            return fixed, 'UTF-8 -> Latin-1 -> GBK'
    except:
        pass
    
    # 方式3: 双重修复 UTF-8 -> Latin-1 -> UTF-8 -> Latin-1 -> UTF-8
    try:
        step1 = content.encode('latin-1').decode('utf-8')
        fixed = step1.encode('latin-1').decode('utf-8')
        if '狼人' in fixed or '身份' in fixed or '预测' in fixed:
            return fixed, '双重修复'
    except:
        pass
    
    # 方式4: GBK -> Latin-1 -> UTF-8
    try:
        # 先用GBK重新读取
        with open(filename, 'r', encoding='gbk') as f:
            gbk_content = f.read()
        fixed = gbk_content.encode('latin-1').decode('utf-8')
        if '狼人' in fixed or '身份' in fixed or '预测' in fixed:
            return fixed, 'GBK -> Latin-1 -> UTF-8'
    except:
        pass
    
    return None, None

for filename in ['main.py', 'schemas.py']:
    print(f'处理 {filename}...')
    
    # 先用UTF-8读取
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    fixed, method = try_fix_encoding(content)
    
    if fixed:
        with open(filename, 'w', encoding='utf-8', newline='\n') as f:
            f.write(fixed)
        print(f'  修复成功! 方法: {method}')
        
        lines = fixed.split('\n')[:5]
        print(f'  前5行:')
        for i, line in enumerate(lines):
            print(f'    {i+1}: {line[:60]}')
    else:
        print(f'  无法自动修复，需要手动处理')
    
    print()
