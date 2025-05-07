import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

class TranslationHistory:
    """
    翻译历史管理器
    
    管理论文翻译的修改历史，支持版本控制和回滚
    """
    
    def __init__(self, output_dir: str):
        """初始化翻译历史管理器
        
        Args:
            output_dir: 输出目录路径
        """
        self.output_dir = output_dir
        self.history_dir = os.path.join(output_dir, "_translation_history")
        os.makedirs(self.history_dir, exist_ok=True)
        
    def save_edit(self, paper_id: str, node_id: str, original_text: str, 
                  edited_text: str, lang: str = "zh") -> bool:
        """保存翻译编辑历史
        
        Args:
            paper_id: 论文ID
            node_id: 节点ID
            original_text: 原始文本
            edited_text: 编辑后文本
            lang: 语言，默认为中文
            
        Returns:
            bool: 保存成功返回True，否则返回False
        """
        try:
            # 创建论文历史目录
            paper_history_dir = os.path.join(self.history_dir, paper_id)
            os.makedirs(paper_history_dir, exist_ok=True)
            
            # 获取当前时间戳作为版本号
            timestamp = int(time.time())
            date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            # 构建历史记录
            edit_record = {
                "node_id": node_id,
                "timestamp": timestamp,
                "date": date_str,
                "lang": lang,
                "original_text": original_text,
                "edited_text": edited_text
            }
            
            # 加载现有历史记录
            history_file = os.path.join(paper_history_dir, f"{node_id}.json")
            history = []
            
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            # 添加新记录
            history.append(edit_record)
            
            # 保存历史记录
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                
            print(f"保存翻译编辑历史: {paper_id}/{node_id}")
            return True
            
        except Exception as e:
            print(f"保存翻译编辑历史失败: {str(e)}")
            return False
            
    def get_edit_history(self, paper_id: str, node_id: str) -> List[Dict]:
        """获取节点的编辑历史
        
        Args:
            paper_id: 论文ID
            node_id: 节点ID
            
        Returns:
            List[Dict]: 编辑历史记录列表，最新的在最后
        """
        history_file = os.path.join(self.history_dir, paper_id, f"{node_id}.json")
        
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"读取编辑历史失败: {str(e)}")
                
        return []
        
    def get_latest_edit(self, paper_id: str, node_id: str) -> Optional[Dict]:
        """获取节点的最新编辑记录
        
        Args:
            paper_id: 论文ID
            node_id: 节点ID
            
        Returns:
            Optional[Dict]: 最新编辑记录，如果没有则返回None
        """
        history = self.get_edit_history(paper_id, node_id)
        
        if history:
            return history[-1]
        
        return None
        
    def rollback_to_version(self, paper_id: str, node_id: str, 
                           timestamp: int) -> Optional[Dict]:
        """回滚到指定版本
        
        Args:
            paper_id: 论文ID
            node_id: 节点ID
            timestamp: 时间戳
            
        Returns:
            Optional[Dict]: 回滚后的编辑记录，如果失败则返回None
        """
        history = self.get_edit_history(paper_id, node_id)
        
        # 找到指定时间戳的版本
        target_version = None
        for record in history:
            if record["timestamp"] == timestamp:
                target_version = record
                break
                
        if target_version is None:
            print(f"未找到指定版本: {timestamp}")
            return None
            
        # 创建回滚记录
        rollback_record = {
            "node_id": node_id,
            "timestamp": int(time.time()),
            "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "lang": target_version["lang"],
            "original_text": history[-1]["edited_text"],  # 当前版本作为原始文本
            "edited_text": target_version["edited_text"],  # 目标版本作为编辑后文本
            "is_rollback": True,
            "rollback_to": timestamp
        }
        
        # 添加回滚记录
        history.append(rollback_record)
        
        # 保存更新的历史记录
        try:
            history_file = os.path.join(self.history_dir, paper_id, f"{node_id}.json")
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                
            print(f"回滚到版本 {timestamp} 成功")
            return rollback_record
            
        except Exception as e:
            print(f"保存回滚记录失败: {str(e)}")
            return None
    
    def export_document(self, paper_id: str, include_history: bool = False) -> Dict:
        """导出包含所有最新翻译的文档
        
        Args:
            paper_id: 论文ID
            include_history: 是否包含编辑历史
            
        Returns:
            Dict: 包含导出信息的字典
        """
        # 构建导出结果
        export_result = {
            "paper_id": paper_id,
            "export_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "nodes": {},
            "history_included": include_history
        }
        
        # 获取论文历史目录
        paper_history_dir = os.path.join(self.history_dir, paper_id)
        
        if not os.path.exists(paper_history_dir):
            print(f"论文 {paper_id} 没有翻译历史")
            return export_result
            
        # 遍历所有节点历史文件
        for filename in os.listdir(paper_history_dir):
            if filename.endswith('.json'):
                node_id = filename[:-5]  # 移除.json后缀
                
                try:
                    history_file = os.path.join(paper_history_dir, filename)
                    with open(history_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                        
                    if history:
                        # 获取最新版本
                        latest = history[-1]
                        
                        # 添加到导出结果
                        export_result["nodes"][node_id] = {
                            "latest_edit": latest["edited_text"],
                            "lang": latest["lang"],
                            "last_edited": latest["date"]
                        }
                        
                        # 如果需要，添加完整历史
                        if include_history:
                            export_result["nodes"][node_id]["history"] = history
                            
                except Exception as e:
                    print(f"读取节点 {node_id} 历史失败: {str(e)}")
        
        return export_result
        
    def save_export(self, export_data: Dict, filename: str = None) -> str:
        """保存导出的文档
        
        Args:
            export_data: 导出数据
            filename: 文件名，如果不提供则自动生成
            
        Returns:
            str: 保存的文件路径
        """
        if filename is None:
            # 自动生成文件名
            paper_id = export_data.get("paper_id", "unknown")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{paper_id}_export_{timestamp}.json"
            
        # 构建导出目录
        export_dir = os.path.join(self.output_dir, "_exports")
        os.makedirs(export_dir, exist_ok=True)
        
        # 保存导出文件
        export_path = os.path.join(export_dir, filename)
        
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
                
            print(f"导出文档已保存至: {export_path}")
            return export_path
            
        except Exception as e:
            print(f"保存导出文档失败: {str(e)}")
            return "" 