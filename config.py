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

# 定义空的API配置模板
API_CONFIG_TEMPLATE = {
    "providers": {
        "xAI": {
            "base_url": "https://api.x.ai/v1",
            "api_key": "",
            "models": {
                "grok-3-beta": {
                    "id": "xai-grok:free but training",
                    "name": "xai-grok",
                    "description": "Grok-3-beta(X.AI)",
                    "model_id": "grok-3-beta"
                }
            }
        },
        "OpenRouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "",
            "models": {}
        },
        "DeepSeek": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "",
            "models": {}
        },
        "Anthropic": {
            "base_url": "https://anthropic.com/v1",
            "api_key": "",
            "models": {}
        },
        "OpenAI": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "models": {}
        }
    },
    "current_model": "xai-grok:free but training",
    "tts": {
        "group_id": "",
        "api_key": ""
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

# 加载API配置
API_CONFIG = ensure_api_config()

# 当前使用的模型配置ID
CURRENT_MODEL_ID = API_CONFIG.get("current_model", "xai-grok:free but training")

# 为兼容旧代码，构建扁平化模型预设映射
def build_model_presets():
    model_presets = {}
    for provider_name, provider in API_CONFIG.get("providers", {}).items():
        for model_key, model in provider.get("models", {}).items():
            model_id = model.get("id", f"{provider_name.lower()}-{model_key}")
            model_presets[model_id] = {
                "name": model.get("name", model_key),
                "description": model.get("description", f"{provider_name} {model_key}"),
                "base_url": provider.get("base_url", ""),
                "api_key": provider.get("api_key", ""),
                "model_id": model.get("model_id", model_key),
                "provider": provider_name
            }
    return model_presets

MODEL_PRESETS = build_model_presets()

# TTS 配置
def get_tts_config():
    """获取TTS配置
    
    Returns:
        tuple: (group_id, api_key)
    """
    tts_config = API_CONFIG.get("tts", {})
    return (
        tts_config.get("group_id", ""),
        tts_config.get("api_key", "")
    )

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
        self.current_preset = CURRENT_MODEL_ID
        self.update_config(preset_name or self.current_preset)
        
    def update_config(self, preset_name):
        """更新模型配置"""
        if preset_name in MODEL_PRESETS:
            preset = MODEL_PRESETS[preset_name]
            self.api_key = preset["api_key"]
            self.base_url = preset["base_url"]
            self.model_id = preset["model_id"]
            self.current_preset = preset_name
            self.provider = preset.get("provider", "")
            
            # 更新OpenAI客户端
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            # 更新配置文件中的当前模型
            self.update_current_model_in_config(preset_name)
            
            return True
        return False
        
    def update_current_model_in_config(self, preset_name):
        """更新配置文件中的当前模型ID"""
        global API_CONFIG, CURRENT_MODEL_ID
        
        # 更新内存中的当前模型ID
        API_CONFIG["current_model"] = preset_name
        CURRENT_MODEL_ID = preset_name
        
        # 更新配置文件
        try:
            with open(API_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(API_CONFIG, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"更新配置文件失败: {str(e)}")
        
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
        
    def get_available_providers(self):
        """获取所有可用的提供商"""
        providers = {}
        for provider_name in API_CONFIG.get("providers", {}).keys():
            # 计算该提供商下的模型数量
            model_count = len(API_CONFIG["providers"][provider_name].get("models", {}))
            if model_count > 0:
                providers[provider_name] = f"{provider_name} ({model_count}个模型)"
        return providers
        
    def get_provider_models(self, provider_name):
        """获取指定提供商下的所有模型"""
        models = {}
        if provider_name in API_CONFIG.get("providers", {}):
            provider = API_CONFIG["providers"][provider_name]
            for model_key, model in provider.get("models", {}).items():
                model_id = model.get("id", "")
                if model_id in MODEL_PRESETS:
                    models[model_id] = model.get("description", model_key)
        return models
        
    def get_current_model(self):
        """获取当前使用的模型信息"""
        model = MODEL_PRESETS.get(self.current_preset, {})
        return model
        
    def get_current_provider(self):
        """获取当前使用的提供商名称"""
        return self.provider
        
    def add_model(self, provider_name, model_key, model_data):
        """向指定提供商添加新模型
        
        Args:
            provider_name: 提供商名称
            model_key: 模型唯一键名
            model_data: 模型数据字典(id, name, description, model_id)
            
        Returns:
            bool: 添加成功返回True，否则返回False
        """
        global API_CONFIG, MODEL_PRESETS
        
        if provider_name not in API_CONFIG.get("providers", {}):
            print(f"提供商 '{provider_name}' 不存在")
            return False
            
        # 添加到API配置
        API_CONFIG["providers"][provider_name]["models"][model_key] = model_data
        
        # 保存到文件
        try:
            with open(API_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(API_CONFIG, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")
            return False
            
        # 重新构建模型预设映射
        MODEL_PRESETS = build_model_presets()
        
        return True

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
    _device: Optional[str] = None
    _last_access_time: float = 0
    _cleanup_threshold: float = 300  # 5分钟未使用则清理
    
    @classmethod
    def get_instance(cls) -> HuggingFaceEmbeddings:
        """获取嵌入模型实例（单例模式）
        
        Returns:
            HuggingFaceEmbeddings: 嵌入模型实例
        """
        import time
        cls._last_access_time = time.time()
        
        if cls._instance is None:
            # 优先使用GPU加速，如果可用的话
            device = "cuda" if cls._is_gpu_available() else "cpu"
            cls._device = device
            
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
                        cls._device = "cpu"
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
            old_device = cls._device or "未知"
            
            # 深度清理模型资源
            try:
                # 尝试访问并清理HuggingFace模型的内部组件
                if hasattr(cls._instance, 'client'):
                    # 清理HuggingFace transformers客户端
                    client = cls._instance.client
                    if hasattr(client, 'model'):
                        model = client.model
                        # 将模型移到CPU并清理
                        if hasattr(model, 'to'):
                            model.to('cpu')
                        if hasattr(model, 'eval'):
                            model.eval()
                        del model
                    if hasattr(client, 'tokenizer'):
                        del client.tokenizer
                    del client
                    
                # 清理langchain包装器本身
                if hasattr(cls._instance, 'model'):
                    del cls._instance.model
                if hasattr(cls._instance, 'tokenizer'):
                    del cls._instance.tokenizer
                if hasattr(cls._instance, 'encode_kwargs'):
                    del cls._instance.encode_kwargs
                if hasattr(cls._instance, 'model_kwargs'):
                    del cls._instance.model_kwargs
                
                # 删除实例引用
                del cls._instance
                
                # 多重垃圾回收确保彻底清理
                import gc
                for _ in range(3):
                    gc.collect()
                
                # 清理CUDA缓存和同步
                import torch
                if torch.cuda.is_available():
                    # 强制清理所有未使用的缓存内存
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
                    # 同步所有CUDA操作
                    torch.cuda.synchronize()
                    
                    # 获取清理后的显存状态
                    allocated = torch.cuda.memory_allocated(0) / (1024**3)
                    reserved = torch.cuda.memory_reserved(0) / (1024**3)
                    logging.info(f"CUDA缓存清理完成 - 已分配: {allocated:.2f}GB, 已保留: {reserved:.2f}GB")
                    
            except Exception as e:
                logging.warning(f"清理嵌入模型资源时出现警告: {str(e)}")
                
            # 重置所有状态
            cls._instance = None
            cls._device = None
            cls._last_access_time = 0
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
                total_memory = torch.cuda.get_device_properties(0).total_memory
                allocated_memory = torch.cuda.memory_allocated(0)
                reserved_memory = torch.cuda.memory_reserved(0)
                
                # 使用reserved而不是allocated来计算真实可用内存
                free_memory = total_memory - reserved_memory
                free_gb = free_memory / (1024**3)
                
                # 对于BGE-m3模型，至少需要4GB显存
                min_required_gb = 4.0
                
                if free_gb >= min_required_gb:
                    logging.info(f"GPU显存充足 (可用: {free_gb:.2f}GB, 已保留: {reserved_memory/(1024**3):.2f}GB, 需要: {min_required_gb:.2f}GB)")
                    return True
                else:
                    logging.warning(f"GPU显存不足 (可用: {free_gb:.2f}GB, 已保留: {reserved_memory/(1024**3):.2f}GB, 需要: {min_required_gb:.2f}GB)，切换到CPU模式")
                    return False
            else:
                return False
        except Exception as e:
            logging.warning(f"检查GPU状态时出错: {str(e)}")
            return False
    
    @classmethod
    def cleanup_if_idle(cls):
        """如果模型空闲超过阈值时间，自动清理"""
        import time
        if cls._instance is not None and cls._last_access_time > 0:
            idle_time = time.time() - cls._last_access_time
            if idle_time > cls._cleanup_threshold:
                logging.info(f"嵌入模型空闲 {idle_time:.1f}秒，自动清理")
                cls.reset_instance()
                return True
        return False
    
    @classmethod
    def force_cleanup(cls):
        """强制清理嵌入模型和显存"""
        logging.info("强制清理嵌入模型资源")
        cls.reset_instance()
        
        # 额外的显存清理
        try:
            import torch
            import gc
            
            # 多轮垃圾回收
            for i in range(5):
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
            
            if torch.cuda.is_available():
                # 获取清理后状态
                allocated = torch.cuda.memory_allocated(0) / (1024**3)
                reserved = torch.cuda.memory_reserved(0) / (1024**3)
                logging.info(f"强制清理完成 - 已分配: {allocated:.2f}GB, 已保留: {reserved:.2f}GB")
                
        except Exception as e:
            logging.warning(f"强制清理时出错: {str(e)}")

# 全局资源清理函数
def cleanup_all_resources():
    """清理所有全局资源，在应用程序退出时调用"""
    logging.info("开始清理所有全局资源...")
    
    try:
        # 清理嵌入模型
        EmbeddingModel.force_cleanup()
        
        # 清理其他可能的全局资源
        import gc
        import torch
        
        # 多轮垃圾回收
        for i in range(3):
            gc.collect()
        
        # 清理CUDA资源
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            torch.cuda.synchronize()
        
        logging.info("全局资源清理完成")
        
    except Exception as e:
        logging.warning(f"清理全局资源时出现警告: {str(e)}")

# 使用示例
if __name__ == "__main__":
    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
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
        
    finally:
        # 确保资源被清理
        cleanup_all_resources()