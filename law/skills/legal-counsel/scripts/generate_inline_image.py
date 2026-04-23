#!/usr/bin/env python3
"""
生成内联图片数据的辅助脚本
用于将宋萌律师的图片转换为可内联的base64数据URL
"""

import base64
import os
from pathlib import Path

def generate_inline_image():
    """生成内联图片的base64数据URL"""
    # 获取脚本所在目录的父目录（即skill目录）
    skill_dir = Path(__file__).parent.parent
    image_path = skill_dir / "assets" / "songmeng_small.jpg"
    
    if not image_path.exists():
        print(f"错误：图片文件不存在: {image_path}")
        return None
    
    # 读取图片并转换为base64
    with open(image_path, "rb") as img_file:
        img_data = img_file.read()
        base64_data = base64.b64encode(img_data).decode('utf-8')
    
    # 生成data URL
    data_url = f"data:image/jpeg;base64,{base64_data}"
    
    return data_url

if __name__ == "__main__":
    data_url = generate_inline_image()
    if data_url:
        print("内联图片生成成功，长度:", len(data_url))
        print("可以在Markdown中使用以下代码:")
        print(f'![宋萌]({data_url})')
    else:
        print("内联图片生成失败")