import os
import itertools

os.chdir(r'D:\project-AI\werewolf_v5\backend')

def find_correct_encoding(filename):
    """尝试所有可能的编码组合"""
    with open(filename, 'rb') as f:
        raw_bytes = f.read()
    
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1', 'cp1252']
    
    # 尝试单次解码
    for enc in encodings:
        try:
            content = raw_bytes.decode(enc)
            if '狼人' in content or '身份' in content or '预测' in content:
                return content, f'直接用 {enc} 解码'
        except:
            continue
    
    # 尝试双重编码组合
    for enc1, enc2 in itertools.product(encodings, repeat=2):
        try:
            step1 = raw_bytes.decode(enc1)
            content = step1.encode(enc2).decode('utf-8')
            if '狼人' in content or '身份' in content or '预测' in content:
                return content, f'{enc1} -> {enc2} -> utf-8'
        except:
            continue
    
    # 尝试三重编码组合
    for enc1, enc2, enc3 in itertools.product(encodings, repeat=3):
        try:
            step1 = raw_bytes.decode(enc1)
            step2 = step1.encode(enc2).decode('latin-1')
            content = step2.encode(enc3).decode('utf-8')
            if '狼人' in content or '身份' in content or '预测' in content:
                return content, f'{enc1} -> {enc2} -> {enc3} -> utf-8'
        except:
            continue
    
    return None, None

for filename in ['main.py', 'schemas.py']:
    print(f'处理 {filename}...')
    
    content, method = find_correct_encoding(filename)
    
    if content:
        with open(filename, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
        print(f'  修复成功! 方法: {method}')
        
        lines = content.split('\n')[:5]
        print(f'  前5行:')
        for i, line in enumerate(lines):
            print(f'    {i+1}: {line[:60]}')
    else:
        print(f'  无法自动修复')
    
    print()
