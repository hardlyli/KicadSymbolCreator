import csv
import os

# ================= 配置区域 =================
INPUT_CSV = 'pins.csv'             # 你的 CSV 文件名
OUTPUT_LIB = 'my_ai_lib.kicad_sym' # 输出的 KiCad 库文件名
SYMBOL_NAME = 'My_AI_Chip'         # 生成的元件名称
PIN_LENGTH = 2.54                  # 引脚长度 (mm)
PIN_SPACING = 2.54                 # 引脚间距 (mm)
BOX_WIDTH = 12.7                   # 元件矩形框宽度的一半 (mm,稍微改宽一点以适应长名字)

# KiCad 电气类型映射表
TYPE_MAP = {
    'Input': 'input',
    'Output': 'output',
    'I/O': 'bidirectional',
    'Bidirectional': 'bidirectional',
    'Power Input': 'power_in',
    'Power': 'power_in',
    'GND': 'power_in',
    'Passive': 'passive',
    'NC': 'no_connect'
}
DEFAULT_TYPE = 'unspecified'

def get_kicad_type(raw_type):
    if not raw_type: return DEFAULT_TYPE
    key = raw_type.strip()
    for k, v in TYPE_MAP.items():
        if k.lower() == key.lower():
            return v
    return DEFAULT_TYPE

def generate_kicad_symbol(csv_file, lib_file, sym_name):
    left_pins = []
    right_pins = []

    print(f"正在读取文件: {csv_file} ...")
    
    if not os.path.exists(csv_file):
        print(f"❌ 错误: 找不到文件 {csv_file}，请确认文件名是否正确。")
        return

    # 使用 utf-8-sig 编码，防止 Windows Excel 导出的 CSV 带有 BOM 乱码
    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            row_count = 0
            for row in reader:
                # 跳过空行或列数不足的行
                if len(row) < 2: continue
                
                # 假设第一列是序号，第二列是名字，第三列是类型(可选)
                pin_num = row[0].strip()
                pin_name = row[1].strip()
                pin_type_raw = row[2].strip() if len(row) > 2 else "Unspecified"
                
                # 如果第一行是标题(例如包含 "Designator" 或 "Pin"), 跳过
                if "Pin" in pin_num or "Name" in pin_name:
                    continue

                k_type = get_kicad_type(pin_type_raw)
                
                # 简单的布局策略
                if k_type in ['input', 'power_in', 'open_collector']:
                    left_pins.append({'num': pin_num, 'name': pin_name, 'type': k_type})
                else:
                    right_pins.append({'num': pin_num, 'name': pin_name, 'type': k_type})
                row_count += 1
                
            print(f"✅ 读取成功，共找到 {row_count} 个引脚。")
            
    except Exception as e:
        print(f"❌ 读取 CSV 出错: {e}")
        return

    max_pins = max(len(left_pins), len(right_pins))
    # 保证框体最小高度，避免太难看
    if max_pins < 2: max_pins = 2
    
    box_height = (max_pins + 1) * PIN_SPACING
    half_height = box_height / 2

    # ============ 生成 S-Expression ============
    content = f'(kicad_symbol_lib (version 20211014) (generator "AI_Script_By_User")\n'
    content += f'  (symbol "{sym_name}" (in_bom yes) (on_board yes)\n'
    content += f'    (property "Reference" "U" (id 0) (at 0 {half_height + 2.54} 0) (effects (font (size 1.27 1.27))))\n'
    content += f'    (property "Value" "{sym_name}" (id 1) (at 0 {half_height + 5.08} 0) (effects (font (size 1.27 1.27))))\n'
    
    # 【重点修复】注意下面这一行，hide 放在了 font 的括号外面
    content += f'    (property "Footprint" "" (id 2) (at 0 -{half_height + 2.54} 0) (effects (font (size 1.27 1.27)) hide))\n'
    content += f'    (property "Datasheet" "" (id 3) (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
    
    content += f'    (symbol "{sym_name}_1_1"\n'

    # 左侧引脚
    y_pos = half_height - PIN_SPACING
    for pin in left_pins:
        content += (
            f'      (pin {pin["type"]} line (at -{BOX_WIDTH + PIN_LENGTH} {y_pos} 0) (length {PIN_LENGTH})\n'
            f'        (name "{pin["name"]}" (effects (font (size 1.27 1.27))))\n'
            f'        (number "{pin["num"]}" (effects (font (size 1.27 1.27))))\n'
            f'      )\n'
        )
        y_pos -= PIN_SPACING

    # 右侧引脚
    y_pos = half_height - PIN_SPACING
    for pin in right_pins:
        content += (
            f'      (pin {pin["type"]} line (at {BOX_WIDTH + PIN_LENGTH} {y_pos} 180) (length {PIN_LENGTH})\n'
            f'        (name "{pin["name"]}" (effects (font (size 1.27 1.27))))\n'
            f'        (number "{pin["num"]}" (effects (font (size 1.27 1.27))))\n'
            f'      )\n'
        )
        y_pos -= PIN_SPACING

    # 矩形框
    content += (
        f'      (rectangle (start -{BOX_WIDTH} {half_height}) (end {BOX_WIDTH} -{half_height})\n'
        f'        (stroke (width 0.254) (type default) (color 0 0 0 0))\n'
        f'        (fill (type background)))\n'
    )

    content += '    )\n' # symbol_1_1
    content += '  )\n'   # symbol
    content += ')\n'     # lib

    with open(lib_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"🎉 成功生成库文件: {lib_file}")
    print("现在请去 KiCad 重新添加这个文件。")

if __name__ == "__main__":
    generate_kicad_symbol(INPUT_CSV, OUTPUT_LIB, SYMBOL_NAME)