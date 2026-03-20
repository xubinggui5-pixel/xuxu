#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import json
import mimetypes
import time
import re
import urllib.parse
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qs
import os
import random
import string
from typing import Optional, Tuple, Dict, Any, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 禁用SSL警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 常量定义
APP_KEY = "12574478"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
ITEM_EDIT_URL = "https://acs.m.goofish.com/h5/mtop.idle.wx.idleitem.edit/1.0/2.0/"

# 会话对象
session = requests.Session()

# 配置重试策略
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# ==================== 固定的utdid ====================
FIXED_UTDID = "Wg4zIi+WPAUCASQGAksSETS9"
# ===================================================


def parse_cookie_string(cookie_str: str) -> dict:
    """解析cookie字符串为字典"""
    cookies = {}
    try:
        items = cookie_str.split(';')
        for item in items:
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                cookies[key.strip()] = value.strip()
    except Exception as e:
        print(f"Cookie解析失败: {str(e)}")
    return cookies


def extract_auth_from_cookie(cookie_str: str) -> dict:
    """从cookie字符串提取认证信息"""
    cookies = parse_cookie_string(cookie_str)
    
    auth_info = {
        "cookies": cookies,
        "headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) UnifiedPCMacWechat(0xf26406f0) XWEB/14304",
            "Accept": "application/json",
            "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
        },
        "utdid": FIXED_UTDID,
    }
    
    # 提取sgcookie
    if 'sgcookie' in cookies:
        auth_info["headers"]["sgcookie"] = cookies['sgcookie']
    
    # 提取_m_h5_tk
    if '_m_h5_tk' in cookies:
        m_h5_tk = cookies['_m_h5_tk']
        auth_info["m_h5_tk"] = m_h5_tk
        auth_info["token"] = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    return auth_info


def download_image_with_fallback(url: str) -> Tuple[bytes, str, str]:
    """下载图片"""
    print(f"📥 下载图片: {url}")
    
    session = requests.Session()
    session.verify = False
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        content = response.content
        if len(content) == 0:
            raise Exception("文件为空")
        
        parsed = urlparse(url)
        file_name = os.path.basename(parsed.path)
        if not file_name or '.' not in file_name:
            file_name = f"image_{int(time.time())}.jpg"
        
        content_type = response.headers.get('Content-Type', '')
        mime = content_type.split(';')[0].strip() or 'image/jpeg'
        
        print(f"   ✅ 下载完成: {len(content)} bytes")
        return content, file_name, mime
        
    except Exception as e:
        print(f"   ❌ 下载失败: {e}")
        raise e


def calc_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算签名"""
    raw = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def upload_bytes(file_name: str, file_bytes: bytes, mime: str, auth_info: dict) -> str:
    """上传文件到闲鱼服务器"""
    global session
    
    cookies = auth_info.get("cookies", {}).copy()
    m_h5_tk = auth_info.get("m_h5_tk", "")
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    # 构建multipart数据
    boundary = '----WebKitFormBoundary' + ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=16))
    
    body = []
    
    # 表单字段
    fields = {
        'name': 'fileFromAlbum',
        'appkey': 'fleamarket',
        'bizCode': 'fleamarket',
        'folderId': '0',
    }
    
    for key, value in fields.items():
        body.append(f'--{boundary}'.encode())
        body.append(f'Content-Disposition: form-data; name="{key}"'.encode())
        body.append(b'')
        body.append(str(value).encode())
    
    # 文件
    body.append(f'--{boundary}'.encode())
    body.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"'.encode())
    body.append(f'Content-Type: {mime}'.encode())
    body.append(b'')
    body.append(file_bytes)
    
    # 结束
    body.append(f'--{boundary}--'.encode())
    body.append(b'')
    
    request_body = b'\r\n'.join(body)
    
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(request_body)),
        'Accept': '*/*',
        'Origin': 'https://servicewechat.com',
        'Referer': 'https://servicewechat.com/wx9882f2a891880616/75/page-frame.html',
        'User-Agent': auth_info.get('headers', {}).get('User-Agent', 'Mozilla/5.0'),
    }
    
    if 'sgcookie' in cookies:
        headers['sgcookie'] = cookies['sgcookie']
    
    params = {
        'folderId': '0',
        'appkey': 'fleamarket',
        '_input_charset': 'utf-8',
    }

    print(f"📤 上传图片...")
    
    response = session.post(
        UPLOAD_URL,
        params=params,
        headers=headers,
        cookies=cookies,
        data=request_body,
        timeout=30,
        verify=False
    )
    
    if response.status_code != 200:
        response.raise_for_status()
    
    body = response.json()
    
    if not body.get('success'):
        error_msg = body.get('message', body.get('errorMsg', '未知错误'))
        raise Exception(f"上传失败: {error_msg}")
    
    image_url = None
    if 'object' in body and 'url' in body['object']:
        image_url = body['object']['url']
    elif 'url' in body:
        image_url = body['url']
    
    if not image_url:
        raise Exception(f"响应中没有图片URL")
    
    print(f"   ✅ 上传成功")
    return image_url


def upload_from_url(file_url: str, auth_info: dict) -> str:
    """从URL上传图片"""
    content, file_name, mime = download_image_with_fallback(file_url)
    return upload_bytes(file_name, content, mime, auth_info)


def update_item_images(item_id: str, image_urls: List[str], auth_info: dict, retry_count: int = 0) -> dict:
    """更新商品图片"""
    global session
    
    cookies = auth_info.get("cookies", {}).copy()
    m_h5_tk = auth_info.get("m_h5_tk", "")
    token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
        cookies["_m_h5_tk_enc"] = "927a61b5898abf557861458d0ea06b6f"
    
    utdid = auth_info.get("utdid", FIXED_UTDID)
    
    # 构建图片信息数组
    image_infos = []
    for i, url in enumerate(image_urls):
        image_infos.append({
            "major": i == 0,
            "widthSize": "1080",
            "heightSize": "1080",
            "type": 0,
            "url": url
        })
    
    # 构建商品数据（最小参数集，只更新图片）
    data_obj = {
        "utdid": utdid,
        "platform": "mac",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
        "imageInfoDOList": image_infos,
    }
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)
    
    t = str(int(time.time() * 1000))
    sign = calc_sign(token, t, APP_KEY, data_str)
    
    params = {
        "jsv": "2.4.12",
        "appKey": APP_KEY,
        "t": t,
        "sign": sign,
        "v": "1.0",
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": "20000",
        "api": "mtop.idle.wx.idleitem.edit",
        "_bx-m": "1",
    }
    
    headers = {
        "User-Agent": auth_info.get('headers', {}).get('User-Agent', 'Mozilla/5.0'),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    }
    
    if 'sgcookie' in cookies:
        headers['sgcookie'] = cookies['sgcookie']
    
    print(f"\n📝 更新商品图片...")
    print(f"商品ID: {item_id}")
    print(f"图片数量: {len(image_urls)}")
    
    response = session.post(
        f"{ITEM_EDIT_URL}?{urlencode(params)}",
        headers=headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20,
        verify=False
    )
    
    result = response.json()
    print(f"   响应: {json.dumps(result, ensure_ascii=False)[:200]}...")
    
    # 自动提取新的 _m_h5_tk 并更新
    token_updated = False
    if '_m_h5_tk' in response.cookies:
        new_m_h5_tk = response.cookies['_m_h5_tk']
        if new_m_h5_tk != m_h5_tk:
            print(f"发现新的 _m_h5_tk: {new_m_h5_tk}")
            auth_info["m_h5_tk"] = new_m_h5_tk
            auth_info["token"] = new_m_h5_tk.split('_')[0] if '_' in new_m_h5_tk else new_m_h5_tk
            auth_info["cookies"]["_m_h5_tk"] = new_m_h5_tk
            token_updated = True
    
    # 如果返回非法令牌且没有重试过，并且token被更新了，则自动重试一次
    if result.get("ret") and ("FAIL_SYS_TOKEN_EMPTY" in str(result["ret"]) or "FAIL_SYS_TOKEN_ILLEGAL" in str(result["ret"])) and retry_count == 0 and token_updated:
        print("\n🔄 检测到新token，自动重试一次...")
        time.sleep(1)
        return update_item_images(item_id, image_urls, auth_info, retry_count=1)
    
    return result


def main():
    print("=" * 60)
    print("🛒 闲鱼商品图片更换工具")
    print("=" * 60)
    
    # 获取Cookie
    print("\n" + "-" * 50)
    print("第一步：请粘贴你的Cookie")
    print("（在闲鱼小程序中复制完整的Cookie字符串）")
    cookie_input = input("Cookie: ").strip()
    
    if not cookie_input:
        print("错误：Cookie不能为空")
        sys.exit(1)
    
    # 解析Cookie
    auth_info = extract_auth_from_cookie(cookie_input)
    
    if not auth_info.get("m_h5_tk"):
        print("错误：未能从Cookie中提取到 _m_h5_tk")
        print("请确保Cookie中包含 _m_h5_tk 字段")
        sys.exit(1)
    
    print(f"\n✅ Cookie解析成功")
    print(f"   utdid: {FIXED_UTDID}")
    print(f"   _m_h5_tk: {auth_info['m_h5_tk'][:50]}...")
    
    # 获取商品ID
    print("\n" + "-" * 50)
    print("第二步：请输入商品ID")
    item_id = input("商品ID: ").strip()
    
    if not item_id:
        print("错误：商品ID不能为空")
        sys.exit(1)
    
    # 获取要更换的图片URL
    print("\n" + "-" * 50)
    print("第三步：请输入新的商品图片URL")
    print("支持多张图片，用逗号分隔，第一张将设为主图")
    print("例如：https://example.com/image1.jpg, https://example.com/image2.jpg")
    
    urls_input = input("图片URL: ").strip()
    
    if not urls_input:
        print("错误：图片URL不能为空")
        sys.exit(1)
    
    image_urls = [url.strip() for url in urls_input.split(',') if url.strip()]
    
    print(f"\n📋 将更新 {len(image_urls)} 张图片")
    for i, url in enumerate(image_urls):
        print(f"   {i+1}. {url[:80]}...")
    
    # 确认操作
    print("\n" + "-" * 50)
    confirm = input("确认执行更换操作？(y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消操作")
        sys.exit(0)
    
    try:
        # 上传所有图片
        uploaded_urls = []
        print("\n" + "=" * 60)
        print("📤 开始上传图片到闲鱼...")
        print("=" * 60)
        
        for i, img_url in enumerate(image_urls):
            print(f"\n处理第 {i+1}/{len(image_urls)} 张图片...")
            final_url = upload_from_url(img_url, auth_info)
            uploaded_urls.append(final_url)
        
        print(f"\n✅ 所有图片上传完成，共 {len(uploaded_urls)} 张")
        
        # 更新商品图片
        print("\n" + "=" * 60)
        print("📝 更新商品图片...")
        print("=" * 60)
        
        result = update_item_images(item_id, uploaded_urls, auth_info)
        
        print("\n" + "=" * 60)
        print("📊 执行结果:")
        print("=" * 60)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if result.get("ret") and "SUCCESS" in str(result["ret"]):
            print("\n✅ 商品图片更新成功！")
        else:
            print("\n⚠️ 商品图片更新可能失败，请检查返回信息")
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()