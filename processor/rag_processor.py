import json
import logging
import os
from pathlib import Path
from typing import Tuple, Dict, List, Any
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain_community.vectorstores.faiss import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from config import EmbeddingModel

class RagProcessor:
    """RAG 处理器：将 JSON 转换为 Markdown 和符合检索需求的JSON树结构，并生成向量库"""

    def __init__(self, output_dir=None):
        """初始化 RAG 处理器
        
        Args:
            output_dir: 输出目录路径，用于生成向量库时确定路径
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.output_dir = output_dir

    def process(self, input_path: str, output_md_path: str, output_tree_json_path: str, vector_store_path: str) -> Tuple[str, str, str]:
        """处理 JSON 文件，生成 Markdown、JSON以及向量库

        Args:
            input_path: 输入JSON文件路径
            output_md_path: 输出的Markdown文件路径
            output_tree_json_path: 输出的树结构JSON文件路径
            vector_store_path: 向量库存储路径

        Returns:
            Tuple[str, str, str]: Markdown文件路径, JSON文件路径, 向量库路径
        """
        self.logger.info(f"开始处理 RAG 数据: {input_path}")

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                paper_data = json.load(f)

            # 提取摘要并放入 summary 字段
            abstract_content = self._extract_abstract_summary(paper_data.get("sections", []))
            abstract_content = self._extract_abstract_summary(paper_data.get("sections", []))
            paper_data["abstract"] = {
                "content": abstract_content.get("content", ""),
                "translated_content": abstract_content.get("translated_content", "")
            }
            
            # 移除 sections 中的 abstract 和 references
            paper_data["sections"] = self._filter_sections(paper_data.get("sections", []))
            
            # 重构树结构
            paper_data = self._restructure_tree(paper_data)
            
            # 生成树结构 JSON
            with open(output_tree_json_path, "w", encoding="utf-8") as f:
                json.dump(paper_data, f, ensure_ascii=False, indent=2)

            # 生成 Markdown 文件
            self._generate_markdown(paper_data, output_md_path)

            # 为 Markdown 文件创建向量库
            self._create_vector_store(output_md_path, vector_store_path)

            self.logger.info("RAG 数据处理完成")
            return output_md_path, output_tree_json_path, vector_store_path

        except Exception as e:
            self.logger.error(f"RAG 处理失败: {str(e)}", exc_info=True)
            raise

    def _create_vector_store(self, md_path: str, vector_store_path: str) -> str:
        """
        为 Markdown 文件创建向量库

        Args:
            md_path: Markdown 文件路径
            vector_store_path: 向量库存储路径

        Returns:
            str: 向量库路径
        """
        self.logger.info(f"开始为 Markdown 创建向量库: {md_path}")
        
        # 确保向量库存储路径存在
        vector_store_path_obj = Path(vector_store_path)
        vector_store_path_obj.mkdir(parents=True, exist_ok=True)
        
        # 读取 Markdown 文件
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 使用 Markdown 标题分割文档
        # 按一级标题分割，这些通常是节点的 key
        headers_to_split_on = [("#", "Header")]
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        docs = md_splitter.split_text(content)
        
        self.logger.info(f"分割后得到 {len(docs)} 个文档片段")
        
        # 尝试使用GPU创建向量存储，如果失败则回退到CPU
        try:
            # 创建向量存储
            vector_store = FAISS.from_documents(
                documents=docs,
                embedding=EmbeddingModel.get_instance(),
                distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT
            )
        except RuntimeError as e:
            # 检查是否是CUDA内存不足错误
            if "CUDA out of memory" in str(e):
                self.logger.warning(f"GPU内存不足，正在切换到CPU模式: {str(e)}")
                
                # 重置嵌入模型实例以强制切换到CPU
                EmbeddingModel.reset_instance()
                
                # 使用CPU模式重试
                try:
                    self.logger.info("使用CPU模式重试创建向量库")
                    vector_store = FAISS.from_documents(
                        documents=docs,
                        embedding=EmbeddingModel.get_instance(),
                        distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT
                    )
                except MemoryError as me:
                    # 处理CPU内存不足的情况
                    self.logger.error(f"CPU内存不足，尝试分批处理: {str(me)}")
                    return self._create_vector_store_in_batches(docs, vector_store_path_obj)
                except Exception as ce:
                    self.logger.error(f"使用CPU创建向量库失败: {str(ce)}")
                    raise
            else:
                # 如果是其他类型的错误，则继续抛出
                raise
        except MemoryError as me:
            # 直接处理GPU模式下的内存错误
            self.logger.error(f"内存不足，尝试分批处理: {str(me)}")
            return self._create_vector_store_in_batches(docs, vector_store_path_obj)
        
        # 保存向量存储
        vector_store.save_local(str(vector_store_path_obj))
        
        self.logger.info(f"向量库创建完成: {vector_store_path_obj}")
        return str(vector_store_path_obj)
        
    def _create_vector_store_in_batches(self, docs, vector_store_path_obj: Path) -> str:
        """
        分批处理方式创建向量库，用于处理内存不足的情况
        
        Args:
            docs: 文档列表
            vector_store_path_obj: 向量库存储路径
            
        Returns:
            str: 向量库路径
        """
        self.logger.info(f"开始分批创建向量库，共 {len(docs)} 个文档")
        
        # 设置批次大小，可以根据实际情况调整
        batch_size = max(1, len(docs) // 4)  # 默认分4批，至少保证每批有1个文档
        vector_store = None
        
        # 确保使用CPU模式
        EmbeddingModel.reset_instance(force_cpu=True)
        embedding_model = EmbeddingModel.get_instance()
        
        for i in range(0, len(docs), batch_size):
            end_idx = min(i + batch_size, len(docs))
            batch_docs = docs[i:end_idx]
            
            self.logger.info(f"处理批次 {i//batch_size + 1}/{(len(docs)-1)//batch_size + 1}，包含 {len(batch_docs)} 个文档")
            
            try:
                # 为当前批次创建向量
                if vector_store is None:
                    # 第一批次，创建新的向量库
                    vector_store = FAISS.from_documents(
                        documents=batch_docs,
                        embedding=embedding_model,
                        distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT
                    )
                else:
                    # 后续批次，合并到现有向量库
                    batch_vector_store = FAISS.from_documents(
                        documents=batch_docs,
                        embedding=embedding_model,
                        distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT
                    )
                    vector_store.merge_from(batch_vector_store)
                
                self.logger.info(f"成功处理批次 {i//batch_size + 1}")
                
            except Exception as e:
                # 如果单批处理仍然失败，尝试进一步减小批次大小
                if batch_size > 1 and isinstance(e, (MemoryError, RuntimeError)):
                    self.logger.warning(f"批处理失败，进一步减小批次大小: {str(e)}")
                    # 递归调用，进一步减小批次大小
                    new_batch_size = max(1, batch_size // 2)
                    if new_batch_size == batch_size:
                        # 已经无法继续减小，只能报错
                        self.logger.error("无法继续减小批次大小，内存不足以处理")
                        raise
                    
                    # 重新调整批次大小的临时文档列表
                    temp_docs = docs[i:] if vector_store else docs
                    
                    if vector_store:
                        # 已经处理了一部分，继续处理剩余部分
                        temp_vector_store = self._create_vector_store_with_custom_batch(temp_docs, new_batch_size)
                        vector_store.merge_from(temp_vector_store)
                    else:
                        # 第一批就失败，重新以更小批次处理全部
                        vector_store = self._create_vector_store_with_custom_batch(temp_docs, new_batch_size)
                    
                    break
                else:
                    # 其他错误，继续抛出
                    self.logger.error(f"创建向量库时发生错误: {str(e)}")
                    raise
        
        if vector_store:
            # 保存合并后的向量库
            vector_store.save_local(str(vector_store_path_obj))
            self.logger.info(f"分批处理完成，成功创建向量库: {vector_store_path_obj}")
            return str(vector_store_path_obj)
        else:
            self.logger.error("未能创建有效的向量库")
            raise RuntimeError("分批处理失败，未能创建向量库")
            
    def _create_vector_store_with_custom_batch(self, docs, batch_size):
        """
        使用自定义批次大小创建向量库
        
        Args:
            docs: 文档列表
            batch_size: 批次大小
            
        Returns:
            FAISS: 创建的向量库
        """
        self.logger.info(f"使用自定义批次大小 {batch_size} 创建向量库，共 {len(docs)} 个文档")
        
        embedding_model = EmbeddingModel.get_instance()
        vector_store = None
        
        for i in range(0, len(docs), batch_size):
            end_idx = min(i + batch_size, len(docs))
            batch_docs = docs[i:end_idx]
            
            try:
                if vector_store is None:
                    vector_store = FAISS.from_documents(
                        documents=batch_docs,
                        embedding=embedding_model,
                        distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT
                    )
                else:
                    batch_vector_store = FAISS.from_documents(
                        documents=batch_docs,
                        embedding=embedding_model,
                        distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT
                    )
                    vector_store.merge_from(batch_vector_store)
                
                self.logger.info(f"成功处理子批次 {i//batch_size + 1}/{(len(docs)-1)//batch_size + 1}")
                
            except Exception as e:
                self.logger.error(f"处理子批次时发生错误: {str(e)}")
                raise
        
        return vector_store

    def rebuild_vector_store(self, paper_id: str, paper_dir: Path) -> bool:
        """
        根据现有的 Markdown 文件重新构建 Faiss 向量库

        Args:
            paper_id: 论文 ID
            paper_dir: 论文对应的输出目录路径

        Returns:
            bool: 如果重建成功则返回 True，否则返回 False
        """
        self.logger.info(f"开始重建 {paper_id} 的向量库")
        
        md_path = paper_dir / f"final_{paper_id}_rag.md"
        vector_store_path = paper_dir / "vectors"

        if not md_path.exists():
            self.logger.error(f"无法重建向量库：Markdown 文件不存在 {md_path}")
            return False

        try:
            # 确保向量库目录存在，如果已存在旧索引，save_local 会覆盖
            vector_store_path.mkdir(parents=True, exist_ok=True) 
            
            # 调用现有的创建函数来重建
            self._create_vector_store(str(md_path), str(vector_store_path))
            self.logger.info(f"成功重建 {paper_id} 的向量库于 {vector_store_path}")
            return True
        except Exception as e:
            self.logger.error(f"重建向量库失败: {paper_id} - {str(e)}", exc_info=True)
            return False

    def _extract_abstract_summary(self, sections: List[Dict]) -> Dict[str, str]:
        """提取摘要，同时返回原文和翻译内容"""
        for section in sections:
            if section.get("type") == "abstract":
                content = []
                translated_content = []
                for item in section.get("content", []):
                    if isinstance(item, dict) and item.get("type") == "text":
                        content.append(item.get("content", ""))
                        translated_content.append(item.get("translated_content", ""))
                return {
                    "content": "\n".join(content),
                    "translated_content": "\n".join(translated_content)
                }
        return {"content": "", "translated_content": ""}

    def _filter_sections(self, sections: List[Dict]) -> List[Dict]:
        """过滤掉 abstract 和 references 类型的章节"""
        filtered_sections = []
        for section in sections:
            if section.get("type") != "abstract" and section.get("type") != "references":
                filtered_sections.append(section)
        return filtered_sections

    def _restructure_tree(self, paper_data: Dict) -> Dict:
        """重构树结构，移除不需要的字段，重新标注索引和层级"""
        # 重新标注节点的 level 和 index
        restructured_sections = self._restructure_sections(paper_data.get("sections", []), level=1)
        
        # 重构后的 paper_data
        restructured_paper = {
            "title": paper_data.get("title", ""),
            "translated_title": paper_data.get("translated_title", ""),
            "abstract": {
                "content": paper_data.get("abstract", {}).get("content", ""),
                "translated_content": paper_data.get("abstract", {}).get("translated_content", "")
            },
            "sections": restructured_sections
        }
        
        # 根据重构后的树生成 key_map
        restructured_paper["key_map"] = self._generate_key_map(restructured_sections, paper_data.get("title", ""))
        
        return restructured_paper

    def _restructure_sections(self, sections: List[Dict], level: int) -> List[Dict]:
        """递归重构章节，移除不需要的字段，重新标注索引和层级"""
        restructured_sections = []
        
        for i, section in enumerate(sections):
            # 创建新的章节字典，仅保留需要的字段
            new_section = {
                "title": section.get("title", ""),
                "translated_title": section.get("translated_title", ""),
                "level": level,
                "summary": section.get("summary", ""),
                "content": []
            }
            
            # 处理内容，重新标注索引
            content_index = 0
            for item in section.get("content", []):
                if isinstance(item, dict):
                    new_item = {
                        "type": item.get("type", ""),
                        "index": content_index
                    }
                    
                    # 根据内容类型保留相应字段
                    if item.get("type") == "text":
                        new_item["content"] = item.get("content", "")
                        new_item["translated_content"] = item.get("translated_content", "")
                        new_item["questions"] = item.get("questions", "")
                    elif item.get("type") == "figure":
                        new_item["src"] = item.get("src", "")
                        new_item["alt"] = item.get("alt", "")
                        new_item["caption"] = item.get("caption", "")
                        new_item["translated_caption"] = item.get("translated_caption", "")
                        new_item["questions"] = item.get("questions", "")
                    elif item.get("type") == "table":
                        new_item["content"] = item.get("content", "")
                        new_item["caption"] = item.get("caption", "")
                        new_item["translated_caption"] = item.get("translated_caption", "")
                        new_item["questions"] = item.get("questions", "")
                    elif item.get("type") == "formula":
                        new_item["content"] = item.get("content", "")
                        new_item["formula_analysis"] = item.get("formula_analysis", "")
                    
                    new_section["content"].append(new_item)
                    content_index += 1
            
            # 处理子章节
            if "children" in section and section["children"]:
                new_section["children"] = self._restructure_sections(section.get("children", []), level + 1)
            else:
                new_section["children"] = []
            
            restructured_sections.append(new_section)
        
        return restructured_sections

    def _generate_key_map(self, sections: List[Dict], title: str, parent_path="", parent_json_path="") -> Dict[str, str]:
        """
        生成 key_map，关键路径映射表
        修复：正确处理子章节的JSON路径
        """
        key_map = {}
        
        for i, section in enumerate(sections):
            section_title = section.get("title", "")
            
            # 构建语义路径和JSON路径
            section_path = f"{parent_path}/{section_title}" if parent_path else section_title
            current_json_path = f"{parent_json_path}/sections/{i}" if not parent_json_path else f"{parent_json_path}/{i}"
            
            # 添加章节的映射
            section_key = f"{title}/{section_path}/section"
            key_map[section_key] = current_json_path
            
            # 为内容生成键
            for j, item in enumerate(section.get("content", [])):
                content_key = f"{section_key}/{j}/{item.get('type', '')}"
                key_map[content_key] = f"{current_json_path}/content/{j}"
            
            # 处理子章节，传递正确的JSON路径
            if section.get("children"):
                # 创建子章节的JSON路径，确保包含children层级
                children_json_path = f"{current_json_path}/children"
                child_key_map = self._generate_key_map(
                    section.get("children", []),
                    title,
                    section_path,
                    children_json_path
                )
                key_map.update(child_key_map)
        
        return key_map

    def _get_node_by_json_path(self, json_path: str, json_data: Dict) -> Any:
        """根据 JSON 路径获取节点，增强错误处理和日志记录"""
        if not json_path:
            self.logger.warning(f"空JSON路径")
            return None
            
        keys = json_path.strip("/").split("/")
        node = json_data
        
        try:
            for i, key in enumerate(keys):
                if isinstance(node, list):
                    try:
                        key = int(key)
                        if 0 <= key < len(node):
                            node = node[key]
                        else:
                            self.logger.warning(f"索引越界: {key}, 路径: {json_path}, 位置: {i+1}/{len(keys)}")
                            return None
                    except (ValueError, IndexError):
                        self.logger.warning(f"无效的列表索引: {key}, 路径: {json_path}, 位置: {i+1}/{len(keys)}")
                        return None
                elif isinstance(node, dict):
                    if key in node:
                        node = node[key]
                    else:
                        self.logger.warning(f"键不存在: {key}, 路径: {json_path}, 位置: {i+1}/{len(keys)}")
                        return None
                else:
                    self.logger.warning(f"无法继续导航, 节点类型: {type(node)}, 路径: {json_path}, 位置: {i+1}/{len(keys)}")
                    return None
        except Exception as e:
            self.logger.error(f"解析JSON路径时出错: {json_path}, 错误: {str(e)}")
            return None
            
        return node

    def _generate_markdown(self, tree_structure: Dict, output_path: str):
        """生成 Markdown 文件，按节点 key 组织内容，并增强错误处理"""
        self.logger.info(f"生成 Markdown 文件: {output_path}")
        
        with open(output_path, "w", encoding="utf-8") as f:
            title = tree_structure.get("title", "")
            
            # 先检查并记录所有未找到的节点
            missing_nodes = []
            for key, json_path in tree_structure.get("key_map", {}).items():
                node = self._get_node_by_json_path(json_path, tree_structure)
                if not node:
                    missing_nodes.append((key, json_path))
                    
            if missing_nodes:
                self.logger.warning(f"找不到以下节点: {missing_nodes[:10]} {'...' if len(missing_nodes) > 10 else ''}")
            
            # 遍历 key_map 生成 Markdown 内容
            for key, json_path in tree_structure.get("key_map", {}).items():
                node = self._get_node_by_json_path(json_path, tree_structure)
                
                if not node:
                    # 已在上面记录了，这里不再重复记录
                    continue
                
                md_content = self._generate_md_content(node, key)
                if md_content:
                    f.write(md_content + "\n\n")
                else:
                    self.logger.warning(f"无法为节点生成Markdown内容: {key}, 路径: {json_path}")
            
            self.logger.info(f"Markdown文件生成完成: {output_path}")

    def _generate_md_content(self, node: Dict, key: str) -> str:
        """
        生成 Markdown 内容，宽松化条件以处理更多类型的内容
        增强容错处理，确保即使内容为空也能生成合理的Markdown
        """
        md_content = f"# {key}\n"
        
        # 不同类型的节点生成不同的内容
        if "summary" in node and "/section" in key:
            md_content += f"{node.get('summary', '')}"
            return md_content
        
        if node.get("type") == "text":
            questions = node.get("questions", "")
            # 首先尝试使用translated_content，如果没有则使用content
            content = node.get("translated_content", "")
            if not content:
                content = node.get("content", "")
            
            if questions or content:
                md_content += f"{questions}\n{content}"
                return md_content
            else:
                # 内容为空时提供默认内容
                md_content += "(文本内容为空)"
                return md_content
        
        if node.get("type") == "figure":
            questions = node.get("questions", "")
            # 尝试使用translated_caption，如果没有则使用caption
            caption = node.get("translated_caption", "")
            if not caption:
                caption = node.get("caption", "")
                
            if questions or caption:
                md_content += f"{questions}\n{caption}"
                return md_content
            else:
                # 内容为空时提供默认内容
                md_content += "(图片描述为空)"
                return md_content
            
        if node.get("type") == "table":
            questions = node.get("questions", "")
            # 尝试使用translated_caption，如果没有则使用caption
            caption = node.get("translated_caption", "")
            if not caption:
                caption = node.get("caption", "")
                
            if questions or caption:
                md_content += f"{questions}\n{caption}"
                return md_content
            elif node.get("content", "").strip():
                # 如果至少有表格内容
                md_content += f"(表格内容，无标题)\n{node.get('content', '')}"
                return md_content
            else:
                # 内容为空时提供默认内容
                md_content += "(表格内容为空)"
                return md_content
        
        if node.get("type") == "formula":
            formula_content = node.get("content", "")
            formula_analysis = node.get("formula_analysis", "")
            
            if formula_content or formula_analysis:
                md_content += f"{formula_content}\n{formula_analysis}"
                return md_content
            else:
                # 内容为空时提供默认内容
                md_content += "(公式内容为空)"
                return md_content
        
        # 如果节点是章节而不是内容项
        if "title" in node and "level" in node:
            title = node.get("title", "")
            translated_title = node.get("translated_title", "")
            summary = node.get("summary", "")
            
            if title or translated_title or summary:
                content = ""
                if title:
                    content += f"**{title}**"
                if translated_title and translated_title != title:
                    content += f" ({translated_title})"
                if summary:
                    content += f"\n\n{summary}"
                
                md_content += content
                return md_content
            else:
                # 内容为空时提供默认内容
                md_content += "(章节内容为空)"
                return md_content
        
        # 增加通用默认返回以避免返回空字符串
        return f"{md_content}\n(不支持的节点类型或内容为空)"
        
        if "summary" in node and "/section" in key:
            md_content += f"{node.get('summary', '')}"
            return md_content
        
        if node.get("type") == "text":
            questions = node.get("questions", "")
            # 首先尝试使用translated_content，如果没有则使用content
            content = node.get("translated_content", "")
            if not content:
                content = node.get("content", "")
            
            if questions or content:
                md_content += f"{questions}\n{content}"
                return md_content
        
        if node.get("type") == "figure":
            questions = node.get("questions", "")
            # 尝试使用translated_caption，如果没有则使用caption
            caption = node.get("translated_caption", "")
            if not caption:
                caption = node.get("caption", "")
                
            if questions or caption:
                md_content += f"{questions}\n{caption}"
                return md_content
            
        if node.get("type") == "table":
            questions = node.get("questions", "")
            # 尝试使用translated_caption，如果没有则使用caption
            caption = node.get("translated_caption", "")
            if not caption:
                caption = node.get("caption", "")
                
            if questions or caption:
                md_content += f"{questions}\n{caption}"
                return md_content
        
        if node.get("type") == "formula":
            formula_content = node.get("content", "")
            formula_analysis = node.get("formula_analysis", "")
            
            if formula_content or formula_analysis:
                md_content += f"{formula_content}\n{formula_analysis}"
                return md_content
        
        # 如果节点是章节而不是内容项
        if "title" in node and "level" in node:
            title = node.get("title", "")
            translated_title = node.get("translated_title", "")
            summary = node.get("summary", "")
            
            if title or translated_title or summary:
                content = ""
                if title:
                    content += f"**{title}**"
                if translated_title and translated_title != title:
                    content += f" ({translated_title})"
                if summary:
                    content += f"\n\n{summary}"
                
                md_content += content
                return md_content
        
        return ""

    def generate_vector_store(self, paper_id: str, rag_tree: Dict) -> bool:
        """
        根据论文ID和RAG树生成向量库
        
        Args:
            paper_id: 论文ID
            rag_tree: RAG树结构
            
        Returns:
            bool: 生成成功返回True，否则返回False
        """
        try:
            self.logger.info(f"开始为论文 {paper_id} 生成向量库")
            
            # 检查输出目录是否设置
            if not self.output_dir:
                self.logger.error("未设置输出目录，无法生成向量库")
                return False
                
            # 构建必要的文件路径
            paper_dir = os.path.join(self.output_dir, paper_id)
            vector_dir = os.path.join(paper_dir, "vectors")
            md_path = os.path.join(paper_dir, f"{paper_id}_md.md")
            tree_path = os.path.join(paper_dir, f"{paper_id}_tree.json")
            
            # 确保目录存在
            os.makedirs(vector_dir, exist_ok=True)
            
            # 如果RAG树不存在，先保存
            if not os.path.exists(tree_path):
                with open(tree_path, "w", encoding="utf-8") as f:
                    json.dump(rag_tree, f, ensure_ascii=False, indent=2)
                self.logger.info(f"已保存RAG树: {tree_path}")
            
            # 根据RAG树生成Markdown
            if not os.path.exists(md_path):
                self._generate_markdown(rag_tree, md_path)
                self.logger.info(f"已生成Markdown: {md_path}")
            
            # 为Markdown生成向量库
            self._create_vector_store(md_path, vector_dir)
            self.logger.info(f"已完成向量库生成: {vector_dir}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"生成向量库失败: {str(e)}", exc_info=True)
            return False


# === 运行示例 ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, 
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    processor = RagProcessor()
    input_json_path = "HUMAN-LIKE_EPISODIC_MEMORY_FOR_INFINITE_CONTEXT_LLMS_extra_info.json"
    output_md_path = "HUMAN-LIKE_EPISODIC_MEMORY.md"
    output_tree_json_path = "HUMAN-LIKE_EPISODIC_MEMORY_tree.json"

    processor.process(input_json_path, output_md_path, output_tree_json_path)