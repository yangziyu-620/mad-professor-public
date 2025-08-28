import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import OrderedDict
from langchain_community.vectorstores.faiss import FAISS
from config import EmbeddingModel
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import gc

# 导入rag_processor用于重新处理
from processor.rag_processor import RagProcessor

class VectorLoadingThread(QThread):
    """用于在后台加载向量库的线程"""
    loading_finished = pyqtSignal(dict)  # 加载完成信号，携带paper_id到路径的映射
    
    def __init__(self, base_path):
        super().__init__()
        self.base_path = base_path
    
    def run(self):
        """执行向量库索引加载"""
        paper_vector_paths = {}
        
        try:
            # 构建索引文件路径
            index_path = Path(self.base_path) / "papers_index.json"
            if not index_path.exists():
                print(f"[WARNING] 论文索引不存在: {index_path}")
                self.loading_finished.emit({})
                return
                
            # 加载索引
            with open(index_path, 'r', encoding='utf-8') as f:
                papers_index = json.load(f)
                
            # 遍历所有论文，记录其向量库路径
            for paper in papers_index:
                paper_id = paper.get('id')
                vector_store_path = paper.get('paths', {}).get('rag_vector_store')
                
                if paper_id and vector_store_path:
                    # 存储论文ID和向量库路径的映射
                    full_path = str(Path(self.base_path) / vector_store_path)
                    paper_vector_paths[paper_id] = full_path
                    
            print(f"[INFO] 预加载了 {len(paper_vector_paths)} 篇论文的向量库路径")
            
            # 发出加载完成信号
            self.loading_finished.emit(paper_vector_paths)
            
        except Exception as e:
            print(f"[ERROR] 预加载向量库路径失败: {str(e)}")
            self.loading_finished.emit({})


class RagRetriever(QObject):
    """RAG检索器，用于从向量库中检索相关内容"""
    
    loading_complete = pyqtSignal(bool)  # 加载完成信号
    
    def __init__(self, base_path=None, max_cache_size=3):
        """
        初始化RAG检索器并预加载所有论文的向量库路径
        
        Args:
            base_path: 基础路径，如果提供则自动预加载所有论文
            max_cache_size: 最大缓存向量库数量，默认为3
        """
        super().__init__()
        # 使用OrderedDict实现LRU缓存
        self.vector_stores = OrderedDict()  # 缓存加载过的向量库: {paper_id: vector_store}
        self.paper_vector_paths = {}  # 论文ID到向量库路径的映射: {paper_id: vector_path}
        self.base_path = base_path
        self.loading_thread = None
        self.rag_trees = OrderedDict()  # 缓存加载过的rag_tree: {paper_id: rag_tree}
        
        # 缓存管理配置
        self.max_cache_size = max_cache_size
        self.max_rag_tree_cache = max_cache_size * 2  # RAG树缓存可以稍多一些，因为占用内存较小
        
        # 如果提供了base_path，则预加载所有论文的索引
        if base_path:
            self.preload_all_papers(base_path)

    def preload_all_papers(self, base_path):
        """
        在后台线程中预加载所有论文的索引和向量库路径
        
        Args:
            base_path: 基础路径
        """
        self.base_path = base_path
        print(f"[INFO] 开始在后台加载论文向量库索引: {base_path}")
        
        # 创建并启动加载线程
        self.loading_thread = VectorLoadingThread(base_path)
        self.loading_thread.loading_finished.connect(self._on_loading_finished)
        self.loading_thread.start()

    def _on_loading_finished(self, paper_vector_paths):
        """处理向量库路径加载完成的回调"""
        self.paper_vector_paths = paper_vector_paths
        print(f"[INFO] 完成论文向量库索引加载，共加载 {len(paper_vector_paths)} 个论文索引")
        self.loading_complete.emit(len(paper_vector_paths) > 0)

    def _manage_vector_cache(self, paper_id):
        """
        管理向量库缓存，实现LRU策略
        
        Args:
            paper_id: 当前要访问的论文ID
        """
        # 如果缓存超过限制，移除最旧的
        while len(self.vector_stores) >= self.max_cache_size:
            oldest_id, oldest_store = self.vector_stores.popitem(last=False)
            print(f"[INFO] 清理向量库缓存: {oldest_id}")
            
            # 尝试释放内存
            try:
                del oldest_store
                gc.collect()  # 强制垃圾回收
                
                # 如果是GPU模式，尝试清理CUDA缓存
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except:
                    pass
            except Exception as e:
                print(f"[WARNING] 清理向量库缓存时出错: {str(e)}")

    def _manage_rag_tree_cache(self, paper_id):
        """
        管理RAG树缓存，实现LRU策略
        
        Args:
            paper_id: 当前要访问的论文ID
        """
        # 如果缓存超过限制，移除最旧的
        while len(self.rag_trees) >= self.max_rag_tree_cache:
            oldest_id, oldest_tree = self.rag_trees.popitem(last=False)
            print(f"[INFO] 清理RAG树缓存: {oldest_id}")
            del oldest_tree

    def clear_cache(self):
        """
        手动清理所有缓存
        """
        print("[INFO] 手动清理所有缓存")
        
        # 清理向量库缓存
        for paper_id, vector_store in self.vector_stores.items():
            try:
                del vector_store
            except:
                pass
        self.vector_stores.clear()
        
        # 清理RAG树缓存
        self.rag_trees.clear()
        
        # 强制垃圾回收
        gc.collect()
        
        # 清理CUDA缓存
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                print("[INFO] 已清理CUDA缓存")
        except:
            pass

    def get_cache_info(self):
        """
        获取缓存信息
        
        Returns:
            dict: 缓存信息
        """
        return {
            "vector_stores_cached": len(self.vector_stores),
            "rag_trees_cached": len(self.rag_trees),
            "max_cache_size": self.max_cache_size,
            "cached_papers": list(self.vector_stores.keys())
        }

    def add_paper(self, paper_id: str, vector_store_path: str) -> bool:
        """
        添加新论文的向量库路径并尝试加载
        
        Args:
            paper_id: 论文ID
            vector_store_path: 向量库路径
            
        Returns:
            bool: 添加成功返回True，否则返回False
        """
        try:
            # 添加论文ID和向量库路径的映射
            self.paper_vector_paths[paper_id] = vector_store_path
            print(f"[INFO] 添加新论文向量库: {paper_id} -> {vector_store_path}")
            
            # 管理缓存大小
            self._manage_vector_cache(paper_id)
            
            # 尝试加载向量库
            vector_store = self.load_vector_store(vector_store_path)
            if vector_store:
                self.vector_stores[paper_id] = vector_store
                print(f"[INFO] 成功加载新论文 {paper_id} 的向量库 (缓存数量: {len(self.vector_stores)}/{self.max_cache_size})")
                return True
            else:
                # 尝试重新创建向量库
                print(f"[WARNING] 无法加载新论文 {paper_id} 的向量库，尝试重新创建...")
                if self._recreate_vector_store(paper_id):
                    # 重新尝试加载
                    vector_store = self.load_vector_store(vector_store_path)
                    if vector_store:
                        self.vector_stores[paper_id] = vector_store
                        print(f"[INFO] 成功重新创建并加载论文 {paper_id} 的向量库")
                        return True
                
                print(f"[WARNING] 无法加载新论文 {paper_id} 的向量库")
                return False
        except Exception as e:
            print(f"[ERROR] 添加新论文 {paper_id} 失败: {str(e)}")
            return False

    def load_vector_store(self, vector_store_path: str) -> Optional[FAISS]:
        """
        加载向量库
        
        Args:
            vector_store_path: 向量库路径
            
        Returns:
            Optional[FAISS]: 向量库对象，加载失败则返回None
        """
        # 检查路径是否存在
        path = Path(vector_store_path)
        if not path.exists():
            print(f"[ERROR] 向量库路径不存在: {vector_store_path}")
            return None
            
        # 检查索引文件是否存在
        if not (path / "index.faiss").exists():
            print(f"[ERROR] 向量库索引文件不存在: {vector_store_path}/index.faiss")
            return None
            
        try:
            # 尝试使用当前的嵌入模型加载向量库
            try:
                vector_store = FAISS.load_local(
                    vector_store_path,
                    EmbeddingModel.get_instance(),
                    allow_dangerous_deserialization=True
                )
                
                print(f"[INFO] 成功加载向量库: {vector_store_path}")
                return vector_store
                
            except RuntimeError as e:
                # 检查是否是CUDA内存不足错误
                if "CUDA out of memory" in str(e):
                    print(f"[WARNING] GPU内存不足，清理缓存后切换到CPU模式: {str(e)}")
                    
                    # 先清理缓存释放内存
                    self.clear_cache()
                    
                    # 重置嵌入模型实例以强制切换到CPU
                    EmbeddingModel.reset_instance()
                    
                    # 使用CPU模式重试
                    print("[INFO] 使用CPU模式重试加载向量库")
                    vector_store = FAISS.load_local(
                        vector_store_path,
                        EmbeddingModel.get_instance(),
                        allow_dangerous_deserialization=True
                    )
                    
                    print(f"[INFO] 成功使用CPU模式加载向量库: {vector_store_path}")
                    return vector_store
                else:
                    # 如果是其他类型的错误，则继续抛出
                    raise
                
        except Exception as e:
            print(f"[ERROR] 加载向量库失败: {str(e)}")
            return None
            
    def _recreate_vector_store(self, paper_id: str) -> bool:
        """
        重新创建向量库
        
        Args:
            paper_id: 论文ID
            
        Returns:
            bool: 创建成功返回True，否则返回False
        """
        try:
            # 获取论文路径信息
            if not self.base_path:
                print("[ERROR] 未设置基础路径，无法重新创建向量库")
                return False
                
            # 从索引文件查找所需路径
            index_path = Path(self.base_path) / "papers_index.json"
            if not index_path.exists():
                print(f"[ERROR] 论文索引不存在: {index_path}")
                return False
                
            # 加载索引
            with open(index_path, 'r', encoding='utf-8') as f:
                papers_index = json.load(f)
            
            # 查找论文
            paper_info = None
            for paper in papers_index:
                if paper.get('id') == paper_id:
                    paper_info = paper
                    break
            
            if not paper_info:
                print(f"[ERROR] 未找到论文 {paper_id} 的信息")
                return False
            
            # 获取必要的路径
            paths = paper_info.get('paths', {})
            json_path = paths.get('json')
            tree_path = paths.get('rag_tree')
            md_path = paths.get('rag_md')
            vector_store_path = paths.get('rag_vector_store')
            
            if not (json_path and vector_store_path):
                print(f"[ERROR] 论文 {paper_id} 缺少必要路径信息")
                return False
            
            # 构建完整路径
            json_full_path = str(Path(self.base_path) / json_path)
            tree_full_path = str(Path(self.base_path) / tree_path) if tree_path else None
            md_full_path = str(Path(self.base_path) / md_path) if md_path else None
            vector_store_full_path = str(Path(self.base_path) / vector_store_path)
            
            # 如果md或tree文件不存在，需要重新构建它们
            if not tree_full_path or not os.path.exists(tree_full_path) or not md_full_path or not os.path.exists(md_full_path):
                print(f"[INFO] 需要重新生成RAG文件: {paper_id}")
                
                # 构建输出目录
                output_dir = Path(vector_store_full_path).parent
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # 重新构建tree和md文件路径
                if not tree_full_path:
                    tree_full_path = str(output_dir / f"{paper_id}_tree.json")
                if not md_full_path:
                    md_full_path = str(output_dir / f"{paper_id}_md.md")
            
            # 确保json文件存在
            if not os.path.exists(json_full_path):
                print(f"[ERROR] 论文源JSON文件不存在: {json_full_path}")
                return False
            
            print(f"[INFO] 开始重新生成向量库: {paper_id}")
            
            # 调用RAG处理器，传递输出目录参数
            rag_processor = RagProcessor(self.base_path)
            try:
                # 尝试使用process方法完整处理
                rag_processor.process(
                    json_full_path, 
                    md_full_path, 
                    tree_full_path, 
                    vector_store_full_path
                )
                
                # 更新索引中的路径
                if paper_info and 'paths' in paper_info:
                    rel_md_path = os.path.relpath(md_full_path, self.base_path)
                    rel_tree_path = os.path.relpath(tree_full_path, self.base_path)
                    paper_info['paths']['rag_md'] = rel_md_path.replace('\\', '/')
                    paper_info['paths']['rag_tree'] = rel_tree_path.replace('\\', '/')
                    
                    # 保存更新后的索引
                    with open(index_path, 'w', encoding='utf-8') as f:
                        json.dump(papers_index, f, ensure_ascii=False, indent=2)
                
                print(f"[INFO] 成功重新生成向量库: {paper_id}")
                return True
            except Exception as e:
                print(f"[ERROR] 重新生成向量库失败: {str(e)}")
                return False
        except Exception as e:
            print(f"[ERROR] 重新创建向量库失败: {str(e)}")
            return False

    def load_rag_tree(self, paper_id: str) -> Dict:
        """
        加载论文的rag_tree
        
        Args:
            paper_id: 论文ID
            
        Returns:
            Dict: 论文的rag_tree结构
        """
        if paper_id in self.rag_trees:
            # 移动到最后（最近使用）
            self.rag_trees.move_to_end(paper_id)
            return self.rag_trees[paper_id]
        
        # 管理RAG树缓存大小
        self._manage_rag_tree_cache(paper_id)
            
        try:
            # 构建rag_tree路径
            if not self.base_path:
                print("[ERROR] 未设置基础路径，无法加载rag_tree")
                return {}
                
            # 从索引文件查找rag_tree路径
            index_path = Path(self.base_path) / "papers_index.json"
            if not index_path.exists():
                print(f"[ERROR] 论文索引不存在: {index_path}")
                return {}
                
            # 加载索引
            with open(index_path, 'r', encoding='utf-8') as f:
                papers_index = json.load(f)
            
            # 查找论文
            rag_tree_path = None
            for paper in papers_index:
                if paper.get('id') == paper_id:
                    rag_tree_path = paper.get('paths', {}).get('rag_tree')
                    break
            
            if not rag_tree_path:
                print(f"[ERROR] 未找到论文 {paper_id} 的rag_tree路径，可能需要重新生成")
                return {}
                
            # 加载rag_tree
            full_path = Path(self.base_path) / rag_tree_path
            if not full_path.exists():
                print(f"[ERROR] rag_tree文件不存在: {full_path}，可能需要重新生成")
                return {}
                
            with open(full_path, 'r', encoding='utf-8') as f:
                rag_tree = json.load(f)
                
            # 缓存rag_tree
            self.rag_trees[paper_id] = rag_tree
            print(f"[INFO] 成功加载论文 {paper_id} 的rag_tree")
            return rag_tree
            
        except Exception as e:
            print(f"[ERROR] 加载rag_tree失败: {str(e)}，可能需要重新生成")
            return {}

    def retrieve(self, query: str, paper_id: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        从指定论文的向量库中检索相关内容
        
        Args:
            query: 查询文本
            paper_id: 论文ID
            top_k: 返回结果数量
            
        Returns:
            List[Tuple[str, float]]: 检索结果列表，每个元素为(文本内容, 分数)
        """
        # 获取该论文的向量库
        vector_store = None
        
        # 检查是否已加载
        if paper_id in self.vector_stores:
            # 移动到最后（最近使用）
            self.vector_stores.move_to_end(paper_id)
            vector_store = self.vector_stores[paper_id]
        else:
            # 管理缓存大小
            self._manage_vector_cache(paper_id)
            
            # 尝试加载
            if paper_id in self.paper_vector_paths:
                vector_store_path = self.paper_vector_paths[paper_id]
                vector_store = self.load_vector_store(vector_store_path)
                if vector_store:
                    self.vector_stores[paper_id] = vector_store
                    print(f"[INFO] 成功缓存论文 {paper_id} 的向量库 (缓存数量: {len(self.vector_stores)}/{self.max_cache_size})")
                else:
                    # 向量库不存在，尝试重新创建
                    print(f"[WARNING] 向量库不存在，尝试重新创建: {paper_id}")
                    if self._recreate_vector_store(paper_id):
                        # 重新尝试加载
                        vector_store = self.load_vector_store(vector_store_path)
                        if vector_store:
                            self.vector_stores[paper_id] = vector_store
                            print(f"[INFO] 成功重新创建并加载论文 {paper_id} 的向量库")
        
        if not vector_store:
            print(f"[WARNING] 未能获取论文 {paper_id} 的向量库")
            return []
            
        try:
            # 执行检索
            try:
                docs_with_scores = vector_store.similarity_search_with_score(
                    query=query,
                    k=top_k
                )
                # 格式化结果
                results = [(doc.page_content, score) for doc, score in docs_with_scores]
                print(f"[INFO] 从论文 {paper_id} 检索到 {len(results)} 条结果")
                return results
            except RuntimeError as e:
                # 检查是否是CUDA内存不足错误
                if "CUDA out of memory" in str(e):
                    print(f"[WARNING] 检索时GPU内存不足，正在切换到CPU模式: {str(e)}")
                    
                    # 重置嵌入模型实例以强制切换到CPU
                    EmbeddingModel.reset_instance()
                    
                    # 重新加载向量库
                    print("[INFO] 使用CPU模式重新加载向量库")
                    vector_store_path = self.paper_vector_paths[paper_id]
                    vector_store = self.load_vector_store(vector_store_path)
                    if vector_store:
                        self.vector_stores[paper_id] = vector_store
                        
                        # 重试检索
                        try:
                            docs_with_scores = vector_store.similarity_search_with_score(
                                query=query,
                                k=top_k
                            )
                            print(f"[INFO] 使用CPU模式成功检索到 {len(docs_with_scores)} 条结果")
                        except Exception as e2:
                            print(f"[ERROR] 使用CPU模式检索失败: {str(e2)}")
                            return []
                    else:
                        print(f"[ERROR] 无法使用CPU模式重新加载向量库")
                        return []
                else:
                    # 如果是其他类型的错误，则继续抛出
                    print(f"[ERROR] 检索失败: {str(e)}")
                    return []
        except Exception as e:
            print(f"[ERROR] 检索失败: {str(e)}")
            return []

    def is_ready(self):
        """检查向量库是否已加载完成"""
        return bool(self.paper_vector_paths)

    def retrieve_with_context(self, query: str, paper_id: str, top_k: int = 5) -> Tuple[str, Dict]:
        """
        从指定论文的向量库中检索相关内容并保留其在原文中的结构
        
        Args:
            query: 查询文本
            paper_id: 论文ID
            top_k: 返回结果数量
            
        Returns:
            Tuple[str, Dict]: (结构化的检索结果, 最佳滚动定位信息)
        """
        # 首先检查是否已完成加载
        if not self.is_ready():
            print("[WARNING] 向量库索引尚未加载完成，无法执行检索")
            return "", None

        # 获取该论文的向量库
        vector_store = None
        
        # 检查是否已加载
        if paper_id in self.vector_stores:
            # 移动到最后（最近使用）
            self.vector_stores.move_to_end(paper_id)
            vector_store = self.vector_stores[paper_id]
        else:
            # 管理缓存大小
            self._manage_vector_cache(paper_id)
            
            # 尝试加载
            if paper_id in self.paper_vector_paths:
                vector_store_path = self.paper_vector_paths[paper_id]
                vector_store = self.load_vector_store(vector_store_path)
                if vector_store:
                    self.vector_stores[paper_id] = vector_store
                    print(f"[INFO] 成功缓存论文 {paper_id} 的向量库 (缓存数量: {len(self.vector_stores)}/{self.max_cache_size})")
                else:
                    # 向量库不存在，尝试重新创建
                    print(f"[WARNING] 向量库不存在，尝试重新创建: {paper_id}")
                    if self._recreate_vector_store(paper_id):
                        # 重新尝试加载
                        vector_store = self.load_vector_store(vector_store_path)
                        if vector_store:
                            self.vector_stores[paper_id] = vector_store
                            print(f"[INFO] 成功重新创建并加载论文 {paper_id} 的向量库")
        
        if not vector_store:
            print(f"[WARNING] 未能获取论文 {paper_id} 的向量库")
            return "", None
            
        try:
            # 加载rag_tree
            rag_tree = self.load_rag_tree(paper_id)
            if not rag_tree:
                # 尝试重新创建
                print(f"[WARNING] RAG树不存在，尝试重新创建: {paper_id}")
                if self._recreate_vector_store(paper_id):
                    # 重新尝试加载
                    rag_tree = self.load_rag_tree(paper_id)
                
                if not rag_tree:
                    print(f"[WARNING] 未能加载论文 {paper_id} 的rag_tree")
                    return "", None
                
            # 移除重试机制，直接执行检索
            try:
                # 执行检索
                docs_with_scores = vector_store.similarity_search_with_score(
                    query=query,
                    k=top_k
                )
            except RuntimeError as e:
                # 检查是否是CUDA内存不足错误
                if "CUDA out of memory" in str(e):
                    print(f"[WARNING] 检索时GPU内存不足，正在切换到CPU模式: {str(e)}")
                    
                    # 重置嵌入模型实例以强制切换到CPU
                    EmbeddingModel.reset_instance()
                    
                    # 重新加载向量库
                    print("[INFO] 使用CPU模式重新加载向量库")
                    vector_store_path = self.paper_vector_paths[paper_id]
                    vector_store = self.load_vector_store(vector_store_path)
                    if vector_store:
                        self.vector_stores[paper_id] = vector_store
                        
                        # 重试检索
                        try:
                            docs_with_scores = vector_store.similarity_search_with_score(
                                query=query,
                                k=top_k
                            )
                            print(f"[INFO] 使用CPU模式成功检索到 {len(docs_with_scores)} 条结果")
                        except Exception as e2:
                            print(f"[ERROR] 使用CPU模式检索失败: {str(e2)}")
                            return "", None
                    else:
                        print(f"[ERROR] 无法使用CPU模式重新加载向量库")
                        return "", None
                else:
                    # 如果是其他类型的错误，则继续抛出
                    print(f"[ERROR] 检索失败: {str(e)}")
                    return "", None
            except Exception as e:
                print(f"[ERROR] 检索失败: {str(e)}")
                return "", None

            # 过滤分数大于0.6的结果 - 保持原有检索逻辑
            filtered_docs = [(doc, score) for doc, score in docs_with_scores if score > 0.6]

            if not filtered_docs:
                print(f"[INFO] 未找到相关分数大于0.6的内容，返回空结果")
                return "", None  # 直接返回空字符串，而不是使用备选检索
                
            # 从metadata中提取路径并通过key_map查找对应内容
            section_paths = []
            # 保存第一个文档的分数（最高分）用于定位判断
            first_doc_score = filtered_docs[0][1] if filtered_docs else 0
            
            for doc, score in filtered_docs:
                if 'Header' in doc.metadata:
                    header_key = doc.metadata['Header']
                    if header_key in rag_tree.get('key_map', {}):
                        section_paths.append(rag_tree['key_map'][header_key])
            
            if not section_paths:
                print("[WARNING] 未找到对应的section路径")
                return "", None  # 同样直接返回空字符串
                
            # 构建检索到的章节内容
            retrieved_sections = {}
            for path in section_paths:
                # 解析路径获取节点
                node = self._get_node_from_path(rag_tree, path)
                if node:
                    # 使用路径作为键，避免重复
                    retrieved_sections[path] = node
                    
                    # 查找紧邻的公式块
                    self._add_adjacent_formulas(rag_tree, path, retrieved_sections)
            
            # 初始化滚动信息为None
            scroll_info = None
            
            # 只有当第一个检索结果分数大于0.65时才生成滚动信息
            if first_doc_score > 0.65 and section_paths:
                first_path = section_paths[0]
                first_node = retrieved_sections.get(first_path)
                if first_node:
                    scroll_info = self._create_scroll_info(first_path, first_node, rag_tree)
                    print(f"[INFO] 激活定位功能，分数: {first_doc_score:.4f}")
            else:
                print(f"[INFO] 不激活定位功能，首个结果分数: {first_doc_score:.4f}")
                
            # 按照路径顺序排序
            sorted_paths = sorted(retrieved_sections.keys())
            
            # 构建 最终结果字符串
            #
            result_parts = ["以下是论文中与您问题最相关的内容:"]

            for path in sorted_paths:
                node = retrieved_sections[path]
                # 构建完整的路径层次标题
                section_title = self._build_section_title(rag_tree, path)
                
                result_parts.append(f"\n## {section_title}")
                
                # 添加节点内容
                if node.get('type') == 'text':
                    result_parts.append(node.get('translated_content', '') or node.get('content', ''))
                elif node.get('type') == 'formula':
                    result_parts.append(node.get('content', ''))
                    if 'formula_analysis' in node:
                        result_parts.append(f"公式解释: {node['formula_analysis']}")
                elif node.get('type') == 'figure':
                    caption = node.get('translated_caption', '') or node.get('caption', '')
                    if caption:
                        result_parts.append(f"图片: {caption}")
                elif node.get('type') == 'table':
                    content = node.get('content', '')
                    caption = node.get('translated_caption', '') or node.get('caption', '')
                    if content:
                        result_parts.append(content)
                    if caption:
                        result_parts.append(f"表格: {caption}")
                elif 'summary' in node:
                    result_parts.append(f"摘要: {node['summary']}")

            return "\n\n".join(result_parts), scroll_info
            
        except Exception as e:
            print(f"[ERROR] 结构化检索失败: {str(e)}")
            return "", None  # 发生异常也直接返回空字符串和None

    def _create_scroll_info(self, path: str, node: Dict, rag_tree: Dict) -> Dict:
        """
        创建滚动定位信息
        
        Args:
            path: 节点路径
            node: 节点数据
            rag_tree: RAG树结构
            
        Returns:
            Dict: 滚动定位信息
        """
        # 默认滚动信息
        scroll_info = {
            'is_title': False,  # 是否是标题
            'zh_content': '',   # 中文内容
            'en_content': '',   # 英文内容
            'node_type': node.get('type', 'unknown')  # 节点类型
        }
        
        # 处理节点类型
        if 'type' not in node:
            # 可能是章节节点，需要找到标题
            if path.startswith('/sections/'):
                parts = path.split('/')
                # 对于章节节点，设置为标题类型
                scroll_info['is_title'] = True
                
                # 获取章节标题
                if 'title' in node:
                    scroll_info['en_content'] = node['title']
                if 'translated_title' in node:
                    scroll_info['zh_content'] = node['translated_title']
                
                return scroll_info
        
        # 根据节点类型设置内容
        if node.get('type') == 'text':
            scroll_info['en_content'] = node.get('content', '')
            scroll_info['zh_content'] = node.get('translated_content', '')
        elif node.get('type') == 'figure' or node.get('type') == 'table':
            scroll_info['en_content'] = node.get('caption', '')
            scroll_info['zh_content'] = node.get('translated_caption', '')
        elif node.get('type') == 'formula':
            # 公式内容在中英文中相同
            scroll_info['en_content'] = node.get('content', '')
            scroll_info['zh_content'] = node.get('content', '')
        
        return scroll_info

    def _get_node_from_path(self, tree: Dict, path: str) -> Dict:
        """
        从路径获取节点内容
        
        Args:
            tree: rag_tree结构
            path: 节点路径，如 /sections/0/content/2
            
        Returns:
            Dict: 节点内容
        """
        try:
            # 移除开头的斜杠
            if path.startswith('/'):
                path = path[1:]
                
            # 分割路径
            parts = path.split('/')
            
            # 从树的根开始遍历
            node = tree
            for part in parts:
                if part.isdigit():
                    part = int(part)
                if isinstance(node, dict) and part in node:
                    node = node[part]
                elif isinstance(node, list) and isinstance(part, int) and part < len(node):
                    node = node[part]
                else:
                    return {}
            
            return node
        except Exception as e:
            print(f"[ERROR] 获取节点失败: {str(e)}")
            return {}
    
    def _add_adjacent_formulas(self, tree: Dict, path: str, retrieved_sections: Dict) -> None:
        """
        添加紧邻的公式块
        
        Args:
            tree: rag_tree结构
            path: 当前节点路径
            retrieved_sections: 已检索的章节字典
        """
        try:
            # 解析路径
            if not path or not path.startswith('/'):
                return
                
            parts = path.split('/')
            # 处理如 /sections/0/content/2 格式的路径
            if len(parts) >= 5 and parts[-2] == 'content':
                current_index = int(parts[-1])
                base_path = '/'.join(parts[:-1])
                
                # 检查前面的块
                if current_index > 0:
                    prev_path = f"{base_path}/{current_index - 1}"
                    prev_node = self._get_node_from_path(tree, prev_path)
                    
                    if prev_node.get('type') == 'formula':
                        retrieved_sections[prev_path] = prev_node
                
                # 检查后面的块
                next_path = f"{base_path}/{current_index + 1}"
                next_node = self._get_node_from_path(tree, next_path)
                
                if next_node and next_node.get('type') == 'formula':
                    retrieved_sections[next_path] = next_node
        except Exception as e:
            print(f"[ERROR] 添加相邻公式块失败: {str(e)}")
    
    def _build_section_title(self, tree: Dict, path: str) -> str:
        """
        构建完整的章节标题
        
        Args:
            tree: rag_tree结构
            path: 节点路径
            
        Returns:
            str: 完整的章节标题
        """
        try:
            # 移除开头的斜杠
            if path.startswith('/'):
                path = path[1:]
                
            # 分割路径
            parts = path.split('/')
            
            # 对于sections路径，构建章节标题
            if len(parts) >= 2 and parts[0] == 'sections':
                section_index = int(parts[1])
                
                # 获取章节
                if 'sections' in tree and section_index < len(tree['sections']):
                    section = tree['sections'][section_index]
                    
                    # 优先使用翻译标题，否则使用原标题
                    title = section.get('translated_title', '') or section.get('title', '')
                    
                    # 如果有子章节
                    if len(parts) >= 4 and parts[2] == 'children':
                        child_index = int(parts[3])
                        
                        # 获取子章节
                        if 'children' in section and child_index < len(section['children']):
                            child = section['children'][child_index]
                            
                            # 子章节标题
                            child_title = child.get('translated_title', '') or child.get('title', '')
                            
                            if child_title:
                                return f"{title} > {child_title}"
                    
                    return title
            
            # 如果无法构建标题，返回简单路径描述
            return f"章节 {path}"
        except Exception as e:
            print(f"[ERROR] 构建章节标题失败: {str(e)}")
            return f"章节 {path}"
    
    def cleanup(self):
        """清理所有资源"""
        try:
            print("[INFO] 开始清理RAG检索器资源...")
            
            # 停止加载线程
            if self.loading_thread and self.loading_thread.isRunning():
                self.loading_thread.requestInterruption()
                self.loading_thread.wait(1000)  # 等待最多1秒
            
            # 清理所有缓存
            self.clear_cache()
            
            # 清理路径映射
            self.paper_vector_paths.clear()
            
            print("[INFO] RAG检索器资源清理完成")
            
        except Exception as e:
            print(f"[WARNING] RAG检索器清理资源时出现警告: {str(e)}")