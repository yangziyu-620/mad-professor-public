import os
import json
import datetime
from typing import List, Dict, Any


class ChatHistoryManager:
    """
    聊天记录管理器
    
    负责保存、加载和管理按论文和日期分类的聊天记录
    """
    
    def __init__(self, base_dir: str = None):
        """初始化聊天记录管理器
        
        Args:
            base_dir: 基础目录路径
        """
        # 设置基础路径
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.history_dir = os.path.join(self.base_dir, "output", "_chat_history")
        
        # 确保目录存在
        os.makedirs(self.history_dir, exist_ok=True)
    
    def save_conversation(self, paper_id: str, conversation: List[Dict[str, Any]]) -> bool:
        """保存论文相关的对话记录
        
        Args:
            paper_id: 论文ID
            conversation: 对话记录列表
            
        Returns:
            bool: 保存成功返回True，否则返回False
        """
        try:
            if not paper_id or not conversation:
                return False
            
            # 确保论文目录存在
            paper_dir = os.path.join(self.history_dir, paper_id)
            os.makedirs(paper_dir, exist_ok=True)
            
            # 创建基于日期的文件名
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            file_name = f"{current_date}.json"
            file_path = os.path.join(paper_dir, file_name)
            
            # 读取已有的对话记录（如果存在）
            existing_conversations = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_conversations = json.load(f)
                except:
                    # 如果文件损坏，使用空记录
                    pass
            
            # 添加新的对话记录
            conversation_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "conversation": conversation
            }
            existing_conversations.append(conversation_data)
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_conversations, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"保存对话记录失败: {str(e)}")
            return False
    
    def load_conversations(self, paper_id: str, date: str = None) -> List[Dict[str, Any]]:
        """加载指定论文和日期的对话记录
        
        Args:
            paper_id: 论文ID
            date: 日期字符串，格式为 YYYY-MM-DD，如果不指定则加载最新的
            
        Returns:
            List[Dict[str, Any]]: 对话记录列表
        """
        try:
            if not paper_id:
                return []
            
            # 构建论文目录路径
            paper_dir = os.path.join(self.history_dir, paper_id)
            if not os.path.exists(paper_dir):
                return []
            
            # 如果没有指定日期，查找最新的对话记录
            if not date:
                # 获取所有对话记录文件
                files = [f for f in os.listdir(paper_dir) if f.endswith('.json')]
                if not files:
                    return []
                
                # 按日期排序文件
                files.sort(reverse=True)
                file_path = os.path.join(paper_dir, files[0])
            else:
                # 使用指定的日期
                file_path = os.path.join(paper_dir, f"{date}.json")
                if not os.path.exists(file_path):
                    return []
            
            # 读取并返回对话记录
            with open(file_path, 'r', encoding='utf-8') as f:
                conversations = json.load(f)
            
            return conversations
        except Exception as e:
            print(f"加载对话记录失败: {str(e)}")
            return []
    
    def get_conversation_dates(self, paper_id: str) -> List[str]:
        """获取指定论文的所有对话日期
        
        Args:
            paper_id: 论文ID
            
        Returns:
            List[str]: 日期字符串列表，格式为 YYYY-MM-DD
        """
        try:
            if not paper_id:
                return []
            
            # 构建论文目录路径
            paper_dir = os.path.join(self.history_dir, paper_id)
            if not os.path.exists(paper_dir):
                return []
            
            # 获取所有JSON文件并提取日期
            dates = [f.replace('.json', '') for f in os.listdir(paper_dir) if f.endswith('.json')]
            
            # 按日期排序（从新到旧）
            dates.sort(reverse=True)
            
            return dates
        except Exception as e:
            print(f"获取对话日期失败: {str(e)}")
            return []
    
    def start_new_conversation(self, paper_id: str) -> bool:
        """开始新的对话
        
        创建一个新的对话记录文件，使用当前时间作为时间戳。
        如果当前日期已经有对话记录，则在文件名中添加时间戳区分。
        
        Args:
            paper_id: 论文ID
            
        Returns:
            bool: 成功返回True，否则返回False
        """
        try:
            if not paper_id:
                return False
            
            # 确保论文目录存在
            paper_dir = os.path.join(self.history_dir, paper_id)
            os.makedirs(paper_dir, exist_ok=True)
            
            # 创建基于日期和时间的文件名
            now = datetime.datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H-%M-%S")
            file_name = f"{date_str}_{time_str}.json"
            file_path = os.path.join(paper_dir, file_name)
            
            # 创建空的对话记录
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"创建新对话失败: {str(e)}")
            return False
    
    def get_all_paper_conversations(self) -> Dict[str, List[str]]:
        """获取所有论文的对话记录
        
        Returns:
            Dict[str, List[str]]: {论文ID: [日期列表]}
        """
        try:
            result = {}
            
            # 确保目录存在
            if not os.path.exists(self.history_dir):
                return result
            
            # 遍历所有论文目录
            for paper_id in os.listdir(self.history_dir):
                paper_path = os.path.join(self.history_dir, paper_id)
                if os.path.isdir(paper_path):
                    # 获取该论文的所有对话日期
                    dates = self.get_conversation_dates(paper_id)
                    if dates:
                        result[paper_id] = dates
            
            return result
        except Exception as e:
            print(f"获取所有论文对话记录失败: {str(e)}")
            return {} 