import csv
import os
import re

# ================= 配置区域 =================
INPUT_CSV = 'pins.csv'
OUTPUT_LIB = 'my_ai_lib.kicad_sym'
SYMBOL_NAME = 'My_AI_Chip'
PIN_LENGTH = 2.54
PIN_SPACING = 2.54
BOX_WIDTH = 15.24  
GAP_SIZE = 2.54    # 组与组之间的空隙

# KiCad 电气类型映射
TYPE_MAP = {
    'Input': 'input', 'Output': 'output', 'I/O': 'bidirectional',
    'Bidirectional': 'bidirectional', 'Power Input': 'power_in',
    'Power': 'power_in', 'GND': 'power_in', 'Passive': 'passive',
    'NC': 'no_connect'
}
DEFAULT_TYPE = 'bidirectional'

def get_kicad_type(raw_type):
    if not raw_type: return DEFAULT_TYPE
    key = raw_type.strip()
    for k, v in TYPE_MAP.items():
        if k.lower() == key.lower(): return v
    return DEFAULT_TYPE

def natural_sort_key(pin):
    text = pin['name']
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

def get_group_name(pin_name):
    """根据引脚名字提取组名，例如 PA0 -> PA, VDD_1 -> POWER"""
    name = pin_name.upper()
    # 优先识别电源和控制类
    if any(x in name for x in ['VDD', 'VSS', 'GND', 'VCC', 'BAT']): return 'POWER'
    if any(x in name for x in ['RST', 'NRST', 'MCLR']): return 'RESET'
    if any(x in name for x in ['OSC', 'XTAL', 'CLK']): return 'CLOCK'
    
    # 识别普通 GPIO (PA, PB, P1, P2...)
    # 匹配开头字母+数字的组合，取字母部分
    match = re.match(r'([A-Z]+)\d+', name)
    if match:
        return match.group(1) # 返回 PA, PB, PC...
    
    return 'OTHER' # 其他杂项

def generate_kicad_symbol(csv_file, lib_file, sym_name):
    # 1. 读取所有引脚
    all_pins = []
    print(f"正在读取文件: {csv_file} ...")
    
    if not os.path.exists(csv_file):
        print(f"❌ 错误: 找不到文件 {csv_file}")
        return

    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2: continue
                pin_num = row[0].strip()
                pin_name = row[1].strip()
                pin_type_raw = row[2].strip() if len(row) > 2 else ""
                
                if "Pin" in pin_num or "Name" in pin_name: continue

                k_type = get_kicad_type(pin_type_raw)
                group = get_group_name(pin_name)
                
                all_pins.append({
                    'num': pin_num, 
                    'name': pin_name, 
                    'type': k_type,
                    'group': group
                })
    except Exception as e:
        print(f"❌ 读取错误: {e}")
        return

    # 2. 对引脚进行排序和分组
    # 先按自然顺序全局排序
    all_pins.sort(key=natural_sort_key)
    
    # 将引脚放入不同的篮子（字典）
    groups = {}
    for pin in all_pins:
        g = pin['group']
        if g not in groups: groups[g] = []
        groups[g].append(pin)

    # 3. 【核心算法】左右天平分配
    left_side_groups = []  # 存的是 key (如 'POWER')
    right_side_groups = [] # 存的是 key (如 'PA')

    # 初始分配：功能引脚在左，GPIO在右
    fixed_left = ['POWER', 'RESET', 'CLOCK']
    sorted_group_keys = sorted(groups.keys()) # 剩下的按字母顺序排 (OTHER, PA, PB...)

    # 先把固定的放进左边篮子
    for k in fixed_left:
        if k in groups:
            left_side_groups.append(k)
    
    # 剩下的全放进右边篮子
    for k in sorted_group_keys:
        if k not in fixed_left:
            right_side_groups.append(k)

    # 计算当前高度（引脚数）
    def get_count(group_keys):
        return sum(len(groups[k]) for k in group_keys)

    # ⚖️ 开始平衡循环 ⚖️
    # 只要右边比左边显著高，就把右边第一组移给左边
    while True:
        left_count = get_count(left_side_groups)
        right_count = get_count(right_side_groups)
        
        # 如果右边空了，或者左边已经比右边多了，停止
        if not right_side_groups or left_count >= right_count:
            break
            
        # 尝试移动右边的第一个候选组 (通常是 PA 或 P0)
        candidate = right_side_groups[0]
        candidate_len = len(groups[candidate])
        
        # 预测：如果移动过去，差距会变小吗？
        diff_current = abs(right_count - left_count)
        diff_after = abs((right_count - candidate_len) - (left_count + candidate_len))
        
        if diff_after < diff_current:
            # 移动！
            popped = right_side_groups.pop(0)
            left_side_groups.append(popped)
            print(f"⚖️ 平衡调整: 将 {popped} 组 ({len(groups[popped])}脚) 从右移到左...")
        else:
            # 再移就过头了，停止
            break

    print(f"✅ 平衡完成。左侧: {get_count(left_side_groups)}脚, 右侧: {get_count(right_side_groups)}脚")

    # 4. 生成坐标和 S-Expression
    max_pins = max(get_count(left_side_groups), get_count(right_side_groups))
    # 加上组间隙的高度补偿 (粗略估算：每组加一个空位)
    gap_count = max(len(left_side_groups), len(right_side_groups))
    
    box_height = (max_pins + gap_count + 2) * PIN_SPACING
    half_height = box_height / 2

    content = f'(kicad_symbol_lib (version 20211014) (generator "AI_Script_By_User_V3")\n'
    content += f'  (symbol "{sym_name}" (in_bom yes) (on_board yes)\n'
    content += f'    (property "Reference" "U" (id 0) (at 0 {half_height + 2.54} 0) (effects (font (size 1.27 1.27))))\n'
    content += f'    (property "Value" "{sym_name}" (id 1) (at 0 {half_height + 5.08} 0) (effects (font (size 1.27 1.27))))\n'
    content += f'    (property "Footprint" "" (id 2) (at 0 -{half_height + 2.54} 0) (effects (font (size 1.27 1.27)) hide))\n'
    content += f'    (symbol "{sym_name}_1_1"\n'

    # --- 绘制左侧 ---
    y_pos = half_height - PIN_SPACING
    for g_name in left_side_groups:
        for pin in groups[g_name]:
            content += (
                f'      (pin {pin["type"]} line (at -{BOX_WIDTH + PIN_LENGTH} {y_pos} 0) (length {PIN_LENGTH})\n'
                f'        (name "{pin["name"]}" (effects (font (size 1.27 1.27))))\n'
                f'        (number "{pin["num"]}" (effects (font (size 1.27 1.27))))\n'
                f'      )\n'
            )
            y_pos -= PIN_SPACING
        y_pos -= GAP_SIZE # 组间空隙

    # --- 绘制右侧 ---
    y_pos = half_height - PIN_SPACING
    for g_name in right_side_groups:
        for pin in groups[g_name]:
            content += (
                f'      (pin {pin["type"]} line (at {BOX_WIDTH + PIN_LENGTH} {y_pos} 180) (length {PIN_LENGTH})\n'
                f'        (name "{pin["name"]}" (effects (font (size 1.27 1.27))))\n'
                f'        (number "{pin["num"]}" (effects (font (size 1.27 1.27))))\n'
                f'      )\n'
            )
            y_pos -= PIN_SPACING
        y_pos -= GAP_SIZE # 组间空隙

    # 矩形框
    content += (
        f'      (rectangle (start -{BOX_WIDTH} {half_height}) (end {BOX_WIDTH} -{half_height})\n'
        f'        (stroke (width 0.254) (type default) (color 0 0 0 0))\n'
        f'        (fill (type background)))\n'
    )

    content += '    )\n  )\n)\n'

    with open(lib_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"🎉 库文件已生成: {lib_file}")

if __name__ == "__main__":
    generate_kicad_symbol(INPUT_CSV, OUTPUT_LIB, SYMBOL_NAME)