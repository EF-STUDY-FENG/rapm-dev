"""测试自动布局检测功能

此脚本演示如何检测屏幕分辨率并生成建议的布局参数。
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.raven_task import detect_screen_resolution, suggest_layout_for_resolution
import json

def main():
    print("=" * 60)
    print("自动布局检测测试")
    print("=" * 60)
    
    # Test resolution detection
    resolution = detect_screen_resolution()
    
    if resolution:
        width, height = resolution
        print(f"\n✓ 成功检测到屏幕分辨率: {width}x{height}")
        print(f"  宽高比: {width/height:.2f}")
        
        # Generate suggestions
        suggested = suggest_layout_for_resolution(width, height)
        print(f"\n建议的布局参数:")
        print(json.dumps(suggested, indent=2, ensure_ascii=False))
        
        # Test different resolutions
        print("\n" + "=" * 60)
        print("不同分辨率的建议参数对比:")
        print("=" * 60)
        
        test_resolutions = [
            (1024, 768, "小屏幕 4:3"),
            (1280, 720, "标准 HD 16:9"),
            (1920, 1080, "全高清 FHD"),
            (2560, 1440, "2K QHD"),
            (3840, 2160, "4K UHD"),
            (3440, 1440, "超宽屏 21:9"),
            (1080, 1920, "竖屏")
        ]
        
        for w, h, label in test_resolutions:
            layout = suggest_layout_for_resolution(w, h)
            print(f"\n{label} ({w}x{h}):")
            print(f"  scale_question: {layout['scale_question']}")
            print(f"  scale_option: {layout['scale_option']}")
            print(f"  option_grid_center_y: {layout['option_grid_center_y']}")
            
    else:
        print("\n✗ 无法检测屏幕分辨率")
        print("  请确保系统支持 PsychoPy monitors 或 tkinter")

if __name__ == '__main__':
    main()
