import logging
import sys
import os
import json
from typing import Optional, List, Dict, Any, Generator
from openai import OpenAI
from langchain_huggingface import HuggingFaceEmbeddings

# # API配置

# 模型预设配置
API_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'api_config.json')
API_CONFIG_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'api_config_template.json')

API_CONFIG_TEMPLATE = {
    "xai-grok:free but training": {
        "name": "xai-grok",
        "description": "Grok-3-beta(X.AI)",
        "base_url": "https://api.x.ai/v1",
        "api_key": "",
        "model_id": "grok-3-beta"
    },
    "openrouter-deepseek:free": {
        "name": "deepseek-v3-0324:free",
        "description": "DeepSeek-V3 (0324版本)",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "model_id": "deepseek/deepseek-chat-v3-0324:free"
    },
    "deepseek-official:paid": {
        "name": "deepseek-official",
        "description": "DeepSeek-V3",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "model_id": "deepseek/deepseek-chat"
    },
    "claude:paid": {
        "name": "claude",
        "description": "Claude 3.5 Sonnet",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",
        "model_id": "claude-3-5-sonnet-20240620"
    },
    # "qwen": {
    #     "name": "qwen",
    #     "description": "通义千问",
    #     "base_url": "https://dashscope.aliyuncs.com/api/v1",
    #     "api_key": "sk-c4194e56a5d14be6a20b99c8e99932be",
    #     "model_id": "qwen-max"
    # },
    "openrouter-qwq-32b:free": {
        "name": "qwq-32b:free",
        "description": "Qwen/QWQ-32B",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "model_id": "qwen/qwq-32b:free"
    },
    "chatgpt-4o-mini:paid": {
        "name": "chatgpt-4o-mini",
        "description": "ChatGPT-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model_id": "gpt-4o-mini"
    }
}

def ensure_api_config():
    if not os.path.exists(API_CONFIG_PATH):
        # 如果配置文件不存在，生成空白模板
        with open(API_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(API_CONFIG_TEMPLATE, f, indent=2, ensure_ascii=False)
        # 生成模板文件供github上传
        with open(API_CONFIG_TEMPLATE_PATH, 'w', encoding='utf-8') as f:
            json.dump(API_CONFIG_TEMPLATE, f, indent=2, ensure_ascii=False)
        print(f"未检测到API配置文件，已生成空白模板: {API_CONFIG_PATH}，请填写API密钥。模板文件: {API_CONFIG_TEMPLATE_PATH}")
    with open(API_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

MODEL_PRESETS = ensure_api_config()

# 当前使用的模型配置
CURRENT_MODEL_PRESET = "xai-grok:free but training"

TTS_GROUP_ID = "1916768832421110363"
TTS_API_KEY = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiJVTkFGeWFuZyIsIlVzZXJOYW1lIjoiVU5BRnlhbmciLCJBY2NvdW50IjoiIiwiU3ViamVjdElEIjoiMTkxNjc2ODgzMjQyOTQ5OTExMiIsIlBob25lIjoiMTg4MTAzODgxNjUiLCJHcm91cElEIjoiMTkxNjc2ODgzMjQyMTExMDM2MyIsIlBhZ2VOYW1lIjoiIiwiTWFpbCI6IiIsIkNyZWF0ZVRpbWUiOiIyMDI1LTA0LTMwIDIxOjQyOjIyIiwiVG9rZW5UeXBlIjoxLCJpc3MiOiJtaW5pbWF4In0.cp00Y73fU4zB5tge9Y0oeReRgyDLWci6FpV3IYRA1Mbimf_UDmPVWfBWg_M-sCTaoYLu_RYVSeXWtFxnfFMPCFXL4ZdE0e7JEbLNFpWwSp9MpKd1LOFxsFVgSfmEQom2dV-OChWB3mOnTcwswjGmPvvWPkysb1XWHb0EHBvQPtslEa9y4AmmH4ks6QREH1a2w77JZRKWrFmjTTRrMAKQ2lT5eEzw72ea54ZNNFXFyFICFIRBnjWyEI7xwR_D_NcB9uD1blbMS1BeYyZRULyIi5qYgxaz1mmemcdT2l_kR7oVCW4-WtbT22M4Fhe71QrofSC6jWkCh-si0kVhtknDSw"

# 嵌入模型配置
EMBEDDING_MODEL_NAME = "BAAI/bge-m3"

# 日志配置
def setup_logging():
    """设置日志配置为控制台输出"""
    # 设置日志格式
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建一个根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 创建并配置控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    
    # 清除任何现有的处理器
    root_logger.handlers.clear()
    # 添加控制台处理器
    root_logger.addHandler(console_handler)

# LLM 客 户 端
class LLMClient:
    _instance: Optional['LLMClient'] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super(LLMClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, preset_name=None):
        """初始化LLM客户端"""
        if self._initialized:
            return
            
        # 初始化
        self._initialized = True
        self.current_preset = CURRENT_MODEL_PRESET
        self.update_config(preset_name or self.current_preset)
        
    def update_config(self, preset_name):
        """更新模型配置"""
        if preset_name in MODEL_PRESETS:
            preset = MODEL_PRESETS[preset_name]
            self.api_key = preset["api_key"]
            self.base_url = preset["base_url"]
            self.model_id = preset["model_id"]
            self.current_preset = preset_name
            
            # 更新OpenAI客户端
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            return True
        return False
        
    def switch_model(self, preset_name):
        """切换到不同的模型预设"""
        if self.update_config(preset_name):
            print(f"已切换到模型: {MODEL_PRESETS[preset_name]['description']}")
            return True
        print(f"切换模型失败: 未找到预设 '{preset_name}'")
        return False
        
    def get_available_models(self):
        """获取所有可用模型预设"""
        return {name: preset["description"] for name, preset in MODEL_PRESETS.items()}
        
    def get_current_model(self):
        """获取当前使用的模型信息"""
        return MODEL_PRESETS.get(self.current_preset, {})
        
    def chat(self, messages: List[Dict[str, Any]], temperature=0.5, stream=True) -> str:
        """与LLM交互
        
        Args:
            messages: 消息列表
            temperature: 温度参数，控制随机性
            stream: 是否使用流式输出
            
        Returns:
            str: LLM响应内容
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=temperature,
                stream=stream
            )
            
            if stream:
                full_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        print(content, end='', flush=True)
                        full_response += content
                print()
                return full_response
            else:
                return response.choices[0].message.content
                
        except Exception as e:
            print(f"LLM调用出错: {str(e)}")
            raise

    def chat_stream_by_sentence(self, messages: List[Dict[str, Any]], temperature=0.5) -> Generator[str, None, str]:
        """与LLM交互，按句子流式返回结果
        
        Args:
            messages: 消息列表
            temperature: 温度参数，控制随机性
            
        Yields:
            str: 每个完整句子
            
        Returns:
            str: 完整响应
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=temperature,
                stream=True
            )
            
            full_response = ""
            current_sentence = ""
            
            # 中文的结束标点 - 这些可以直接作为句子结束符
            cn_end_marks = '。！？'
            # 英文的结束标点 - 这些需要检查后续字符
            en_end_marks = '.!?;'
            
            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    current_sentence += content
                    full_response += content
                    
                    # 情况1: 包含中文结束标点，直接作为句子结束
                    if any(char in cn_end_marks for char in content):
                        sentence = current_sentence.strip()
                        # 只有句子长度超过10字才yield
                        if sentence and len(sentence) >= 10:
                            yield sentence
                            current_sentence = ""
                    
                    # 情况2: 检查英文结束标点后是否跟着空格或换行符
                    elif any(char in en_end_marks for char in content):
                        # 检查当前积累的句子中是否有 "英文结束标点+空格/换行" 的模式
                        import re
                        # 匹配 句点/感叹号/问号/分号 后跟空白字符的模式
                        matches = list(re.finditer(r'[.!?;][\s\n]', current_sentence))
                        
                        if matches:
                            # 找到最后一个匹配，在该位置分割句子
                            last_match = matches[-1]
                            end_position = last_match.end() - 1  # 减1是为了不包含空格/换行符
                            
                            sentence = current_sentence[:end_position].strip()
                            remaining = current_sentence[end_position:].strip()
                            
                            # 只有句子长度超过10字才yield
                            if sentence and len(sentence) >= 10:
                                yield sentence
                                current_sentence = remaining
            
            # 处理剩余内容
            if current_sentence.strip():
                sentence = current_sentence.strip()
                if sentence:
                    yield sentence
            
            return full_response
                
        except Exception as e:
            print(f"LLM调用出错: {str(e)}")
            yield f"生成回复时出错: {str(e)}"
            raise


# 嵌入模型
class EmbeddingModel:
    _instance: Optional[HuggingFaceEmbeddings] = None
    
    @classmethod
    def get_instance(cls) -> HuggingFaceEmbeddings:
        """获取嵌入模型实例（单例模式）
        
        Returns:
            HuggingFaceEmbeddings: 嵌入模型实例
        """
        if cls._instance is None:
            # 优先使用GPU加速，如果可用的话
            device = "cuda" if cls._is_gpu_available() else "cpu"
            
            logging.info(f"初始化嵌入模型 {EMBEDDING_MODEL_NAME}，使用设备: {device}")
            
            try:
                # 尝试初始化嵌入模型
                cls._instance = HuggingFaceEmbeddings(
                    model_name=EMBEDDING_MODEL_NAME,
                    model_kwargs={"device": device},
                    encode_kwargs={"device": device, "batch_size": 8}
                )
                logging.info(f"嵌入模型初始化成功")
            except Exception as e:
                # 如果GPU初始化失败，回退到CPU
                if device == "cuda":
                    logging.warning(f"GPU初始化失败: {str(e)}，尝试使用CPU")
                    try:
                        cls._instance = HuggingFaceEmbeddings(
                            model_name=EMBEDDING_MODEL_NAME,
                            model_kwargs={"device": "cpu"},
                            encode_kwargs={"device": "cpu", "batch_size": 8}
                        )
                        logging.info(f"使用CPU成功初始化嵌入模型")
                    except Exception as e2:
                        logging.error(f"CPU初始化也失败: {str(e2)}")
                        raise
                else:
                    logging.error(f"嵌入模型初始化失败: {str(e)}")
                    raise
        
        return cls._instance
    
    @classmethod
    def reset_instance(cls, force_cpu=False):
        """重置嵌入模型实例，使下次获取时重新初始化
        
        Args:
            force_cpu: 是否强制使用CPU，即使GPU可用
        """
        if cls._instance is not None:
            # 保存原设备信息用于日志
            old_device = getattr(cls._instance, "_device", "未知")
            
            # 清理旧实例
            try:
                # 尝试清理CUDA内存
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception as e:
                logging.warning(f"清理CUDA缓存失败: {str(e)}")
                
            # 重置实例
            cls._instance = None
            logging.info(f"已重置嵌入模型实例 (原设备: {old_device})")
            
            # 如果强制使用CPU，先修改设备检测方法
            if force_cpu:
                # 暂存原始方法
                original_is_gpu_available = cls._is_gpu_available
                
                # 创建临时方法强制返回False
                @classmethod
                def force_cpu_detection(c):
                    logging.info("强制使用CPU模式")
                    return False
                
                # 替换方法
                cls._is_gpu_available = force_cpu_detection
                
                # 初始化实例
                instance = cls.get_instance()
                
                # 恢复原始方法
                cls._is_gpu_available = original_is_gpu_available
                
                return instance
    
    @classmethod
    def _is_gpu_available(cls) -> bool:
        """检查GPU是否可用
        
        Returns:
            bool: 如果GPU可用返回True，否则返回False
        """
        try:
            import torch
            if torch.cuda.is_available():
                # 检查GPU可用显存
                free_memory = torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)
                free_gb = free_memory / (1024**3)
                
                # 对于BGE-m3模型，至少需要4GB显存
                min_required_gb = 4.0
                
                if free_gb >= min_required_gb:
                    logging.info(f"GPU显存充足 (可用: {free_gb:.2f}GB, 需要: {min_required_gb:.2f}GB)")
                    return True
                else:
                    logging.warning(f"GPU显存不足 (可用: {free_gb:.2f}GB, 需要: {min_required_gb:.2f}GB)，切换到CPU模式")
                    return False
            else:
                return False
        except Exception as e:
            logging.warning(f"检查GPU状态时出错: {str(e)}")
            return False

# 使用示例
if __name__ == "__main__":
    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # LLM客户端示例
    logger.info("测试LLM客户端...")
    llm = LLMClient()
    messages = [
        {"role": "user", "content": "你好"}
    ]
    response = llm.chat(messages)
    logger.info(f"LLM响应: {response}")
    
    # 嵌入模型示例
    logger.info("测试嵌入模型...")
    text = "这是一个测试文本"
    embedding_model = EmbeddingModel.get_instance()
    embedding = embedding_model.embed_query(text)
    logger.info(f"嵌入向量维度: {len(embedding)}")