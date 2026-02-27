#!/usr/bin/env python3
"""
测试图灵云 OCR 集成
用于验证凭证和 API 连接
"""

import os
import sys
import logging

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from utils.tulingcloud_ocr import TulingCloudOCR

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def test_credentials():
    """测试凭证是否正确配置"""
    print("=" * 60)
    print("图灵云 OCR 测试")
    print("=" * 60)
    
    username = os.getenv("TULINGCLOUD_USERNAME", "")
    password = os.getenv("TULINGCLOUD_PASSWORD", "")
    model_id = os.getenv("TULINGCLOUD_MODEL_ID", "")
    
    print("\n[1] 检查凭证配置")
    print(f"  Username: {username if username else '❌ 未设置'}")
    print(f"  Password: {'✓ 已设置' if password else '❌ 未设置'}")
    print(f"  Model ID: {model_id if model_id else '❌ 未设置'}")
    
    if not all([username, password, model_id]):
        print("\n❌ 凭证不完整！")
        print("\n请按照以下步骤配置：")
        print("  1. 访问 http://www.tulingcloud.com/")
        print("  2. 获取账户名、密码和模型 ID")
        print("  3. 在项目根目录创建 .env 文件或设置环境变量：")
        print("     export TULINGCLOUD_USERNAME='你的账户名'")
        print("     export TULINGCLOUD_PASSWORD='你的密码'")
        print("     export TULINGCLOUD_MODEL_ID='12345678'")
        print("  4. 重新运行此脚本")
        return False
    
    print("\n✓ 凭证配置正确！")
    return True


def test_api_connection(username, password, model_id):
    """测试 API 连接"""
    print("\n[2] 测试 API 连接")
    
    try:
        ocr = TulingCloudOCR(
            username=username,
            password=password,
            model_id=model_id
        )
        print(f"  ✓ OCR 对象创建成功")
        return True
    except Exception as e:
        print(f"  ❌ 创建 OCR 对象失败: {e}")
        return False


def test_recognition_with_sample(ocr):
    """使用示例图片测试识别"""
    print("\n[3] 测试识别功能")
    
    # 创建一个简单的测试图片（1x1 像素的 JPEG）
    test_img_path = "test_sample.jpg"
    
    # 创建一个最小的 JPEG 图片用于测试
    # 这只是为了测试 API 连接，不用期望有正确的识别结果
    try:
        # 最小的 JPEG 头
        minimal_jpeg = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c'
            b'\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c'
            b'\x1c $.\'\ ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00'
            b'\x01\x00\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01'
            b'\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06'
            b'\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03'
            b'\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06'
            b'\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t'
            b'\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz'
            b'\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a'
            b'\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9'
            b'\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8'
            b'\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5'
            b'\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfe\xfe\xfe'
            b'\xff\xd9'
        )
        
        with open(test_img_path, 'wb') as f:
            f.write(minimal_jpeg)
        
        print(f"  📝 创建测试图片: {test_img_path}")
        
        with open(test_img_path, 'rb') as f:
            img_data = f.read()
        
        print(f"  📤 发送识别请求...")
        result = ocr.recognize_textclick(img_data)
        
        if result:
            print(f"  ✓ API 响应成功: {result}")
            print(f"  📝 注意: 这是测试图片，识别结果可能不准确")
            return True
        else:
            print(f"  ⚠️  API 响应但未识别到文字（可能是测试图片的问题）")
            print(f"     这是正常的，说明 API 连接成功")
            return True
            
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        import traceback
        logging.debug(traceback.format_exc())
        return False
    finally:
        # 清理测试文件
        if os.path.exists(test_img_path):
            os.remove(test_img_path)


def main():
    # 测试凭证配置
    if not test_credentials():
        return 1
    
    username = os.getenv("TULINGCLOUD_USERNAME")
    password = os.getenv("TULINGCLOUD_PASSWORD")
    model_id = os.getenv("TULINGCLOUD_MODEL_ID")
    
    # 测试 API 连接
    if not test_api_connection(username, password, model_id):
        return 1
    
    ocr = TulingCloudOCR(
        username=username,
        password=password,
        model_id=model_id
    )
    
    # 测试识别功能
    if not test_recognition_with_sample(ocr):
        return 1
    
    print("\n" + "=" * 60)
    print("✓ 所有测试通过！")
    print("=" * 60)
    print("\n现在你可以运行完整的座位预约脚本了：")
    print("  python3 test_token_lifetime.py")
    print("\n然后选择选项 6 来测试选字验证码识别。")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
