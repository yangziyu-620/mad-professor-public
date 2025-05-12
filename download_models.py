import json
import shutil
import os
import socket
import requests
# 从modelscope和huggingface都导入下载函数
from modelscope import snapshot_download as ms_snapshot_download
from huggingface_hub import snapshot_download as hf_snapshot_download


def is_china_ip():
    """
    检测当前IP是否为中国IP
    返回: True为中国IP，False为非中国IP
    """
    try:
        # 使用淘宝IP接口
        response = requests.get('http://ip.taobao.com/outGetIpInfo?ip=myip&accessKey=alibaba-inc', timeout=5)
        if response.status_code == 200:
            result = response.json()
            if result.get('data', {}).get('country_id') == 'CN':
                return True
        
        # 备选检测方法
        response = requests.get('https://forge.speedtest.cn/api/location/info', timeout=5)
        if response.status_code == 200:
            result = response.json()
            if result.get('country') == '中国':
                return True
            
        return False
    except Exception as e:
        print(f"IP检测出错: {e}")
        # 出错时默认使用HuggingFace
        return False


def download_json(url):
    # 下载JSON文件
    response = requests.get(url)
    response.raise_for_status()  # 检查请求是否成功
    return response.json()


def download_and_modify_json(url, local_filename, modifications):
    if os.path.exists(local_filename):
        data = json.load(open(local_filename))
        config_version = data.get('config_version', '0.0.0')
        if config_version < '1.2.0':
            data = download_json(url)
    else:
        data = download_json(url)

    # 修改内容
    for key, value in modifications.items():
        data[key] = value

    # 保存修改后的内容
    with open(local_filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


if __name__ == '__main__':
    root_dir = os.path.dirname(os.path.abspath(__file__))  # 当前脚本所在目录
    local_model_dir = os.path.join(root_dir, 'models')     # 根目录下 models 文件夹

    # 需要下载的模型文件模式
    mineru_patterns = [
        # "models/Layout/LayoutLMv3/*",
        "models/Layout/YOLO/*",
        "models/MFD/YOLO/*",
        "models/MFR/unimernet_hf_small_2503/*",
        "models/OCR/paddleocr_torch/*",
        # "models/TabRec/TableMaster/*",
        # "models/TabRec/StructEqTable/*",
    ]
    
    # 检测是否为中国IP
    is_cn_ip = is_china_ip()
    
    if is_cn_ip:
        # 使用ModelScope下载模型（中国IP）
        print(f"检测到中国IP，使用ModelScope下载PDF提取模型到目录: {local_model_dir}")
        model_dir = ms_snapshot_download(
            'opendatalab/PDF-Extract-Kit-1.0',
            allow_patterns=mineru_patterns,
            local_dir=local_model_dir
        )
        
        print(f"检测到中国IP，使用ModelScope下载layoutreader模型到目录: {local_model_dir}")
        layoutreader_model_dir = ms_snapshot_download(
            'ppaanngggg/layoutreader',
            local_dir=local_model_dir
        )
    else:
        # 使用HuggingFace下载模型（非中国IP）
        print(f"检测到非中国IP，使用HuggingFace下载PDF提取模型到目录: {local_model_dir}")
        model_dir = hf_snapshot_download(
            repo_id='opendatalab/PDF-Extract-Kit-1.0',
            allow_patterns=mineru_patterns,
            local_dir=local_model_dir,
            max_workers=4  # 适当增加线程数以提高下载速度
        )
        
        print(f"检测到非中国IP，使用HuggingFace下载layoutreader模型到目录: {local_model_dir}")
        layoutreader_model_dir = hf_snapshot_download(
            repo_id='hantian/layoutreader',
            local_dir=local_model_dir,
            max_workers=4
        )
    
    model_dir = model_dir + '/models'
    print(f'model_dir is: {model_dir}')
    print(f'layoutreader_model_dir is: {layoutreader_model_dir}')

    # paddleocr_model_dir = model_dir + '/OCR/paddleocr'
    # user_paddleocr_dir = os.path.expanduser('~/.paddleocr')
    # if os.path.exists(user_paddleocr_dir):
    #     shutil.rmtree(user_paddleocr_dir)
    # shutil.copytree(paddleocr_model_dir, user_paddleocr_dir)

    json_url = 'https://gcore.jsdelivr.net/gh/opendatalab/MinerU@master/magic-pdf.template.json'
    config_file_name = 'magic-pdf.json'
    home_dir = os.path.expanduser('~')
    config_file = os.path.join(home_dir, config_file_name)

    json_mods = {
        'models-dir': model_dir,
        'layoutreader-model-dir': layoutreader_model_dir,
    }

    download_and_modify_json(json_url, config_file, json_mods)
    print(f'The configuration file has been configured successfully, the path is: {config_file}')
