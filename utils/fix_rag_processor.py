import json
import os
import sys
from processor.rag_processor import RagProcessor

def backup_file(file_path):
    """
    备份文件
    
    Args:
        file_path: 要备份的文件路径
        
    Returns:
        备份文件路径
    """
    backup_path = f"{file_path}.bak"
    try:
        import shutil
        shutil.copy2(file_path, backup_path)
        print(f"已备份原文件到: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"备份文件失败: {str(e)}")
        return None

def patch_generate_md_content():
    """
    修补生成Markdown内容的方法，增强容错能力
    
    Returns:
        bool: 修补成功返回True，否则返回False
    """
    try:
        # 找到rag_processor.py文件
        base_dir = os.path.dirname(os.path.abspath(__file__))
        processor_path = os.path.join(base_dir, "processor", "rag_processor.py")
        
        if not os.path.exists(processor_path):
            print(f"找不到 rag_processor.py 文件: {processor_path}")
            return False
            
        # 备份文件
        backup_path = backup_file(processor_path)
        if not backup_path:
            return False
            
        # 读取文件内容
        with open(processor_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 定位_generate_md_content方法
        method_start = content.find("def _generate_md_content")
        if method_start == -1:
            print("找不到 _generate_md_content 方法")
            return False
            
        # 找到方法结束位置
        method_content = content[method_start:]
        indent_level = 0
        for i, line in enumerate(method_content.split('\n')):
            if i == 0:  # 第一行是方法定义
                indent_level = len(line) - len(line.lstrip())
                continue
                
            # 如果是空行或者注释行，跳过
            if not line.strip() or line.strip().startswith('#'):
                continue
                
            # 检查当前行的缩进
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= indent_level and i > 1:  # 找到了方法结束
                method_end = method_start + method_content[:method_content.find('\n', method_content.find('\n', 0) + 1) + i].rfind('\n')
                break
        else:
            # 如果没有找到结束位置，假设方法持续到文件结尾
            method_end = len(content)
            
        # 提取方法内容
        method_content = content[method_start:method_end]
        
        # 修改方法内容
        patched_method = """def _generate_md_content(self, node: Dict, key: str) -> str:
        \"\"\"
        生成 Markdown 内容，宽松化条件以处理更多类型的内容
        增强容错处理，确保即使内容为空也能生成合理的Markdown
        \"\"\"
        md_content = f"# {key}\\n"
        
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
                md_content += f"{questions}\\n{content}"
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
                md_content += f"{questions}\\n{caption}"
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
                md_content += f"{questions}\\n{caption}"
                return md_content
            elif node.get("content", "").strip():
                # 如果至少有表格内容
                md_content += f"(表格内容，无标题)\\n{node.get('content', '')}"
                return md_content
            else:
                # 内容为空时提供默认内容
                md_content += "(表格内容为空)"
                return md_content
        
        if node.get("type") == "formula":
            formula_content = node.get("content", "")
            formula_analysis = node.get("formula_analysis", "")
            
            if formula_content or formula_analysis:
                md_content += f"{formula_content}\\n{formula_analysis}"
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
                    content += f"\\n\\n{summary}"
                
                md_content += content
                return md_content
            else:
                # 内容为空时提供默认内容
                md_content += "(章节内容为空)"
                return md_content
        
        # 增加通用默认返回以避免返回空字符串
        return f"{md_content}\\n(不支持的节点类型或内容为空)"
        """
        
        # 替换方法
        new_content = content[:method_start] + patched_method + content[method_end:]
        
        # 写回文件
        with open(processor_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print("成功修补 _generate_md_content 方法，增强了容错能力")
        
        return True
        
    except Exception as e:
        print(f"修补失败: {str(e)}")
        return False

def test_generate_markdown():
    """
    测试生成Markdown功能
    """
    try:
        # 导入RagProcessor
        from processor.rag_processor import RagProcessor
        
        # 创建一个测试节点
        test_node = {
            "type": "table",
            "content": "",
            "caption": "",
            "translated_caption": ""
        }
        
        # 实例化RagProcessor
        processor = RagProcessor()
        
        # 调用生成Markdown方法
        key = "test/table"
        result = processor._generate_md_content(test_node, key)
        
        print("\n测试结果:")
        print(f"节点类型: {test_node.get('type')}")
        print(f"生成Markdown: {result}")
        
        if result and len(result) > 5:  # 判断生成结果是否有效
            print("\n测试成功：方法已修复，能够处理空内容的节点")
        else:
            print("\n测试失败：方法仍然无法处理空内容的节点")
        
    except Exception as e:
        print(f"\n测试失败: {str(e)}")

def fix_node_in_tree(file_path, node_path, fix_mode="add_placeholder"):
    """
    修复树中的特定节点
    
    Args:
        file_path: RAG树文件路径
        node_path: 要修复的节点路径
        fix_mode: 修复模式，可选值为:
                  - add_placeholder: 添加占位符文本
                  - remove_node: 移除节点
                  
    Returns:
        bool: 修复成功返回True，否则返回False
    """
    try:
        # 加载RAG树
        with open(file_path, 'r', encoding='utf-8') as f:
            rag_tree = json.load(f)
        
        # 解析路径
        if node_path.startswith('/'):
            node_path = node_path[1:]
        path_parts = node_path.split('/')
        
        # 查找父节点和目标节点索引
        parent_path_parts = path_parts[:-1]
        parent_node = None
        
        # 处理特殊情况
        if len(path_parts) > 1:
            # 初始节点
            current_node = rag_tree
            
            # 循环遍历路径
            for i, part in enumerate(path_parts[:-1]):
                if part == "sections" and "sections" in current_node:
                    if i + 1 < len(path_parts):
                        try:
                            idx = int(path_parts[i+1])
                            if idx < len(current_node["sections"]):
                                if i + 1 == len(path_parts) - 1:  # 最后一层
                                    parent_node = current_node["sections"]
                                    break
                                current_node = current_node["sections"][idx]
                                # 跳过索引
                                i += 1
                            else:
                                print(f"索引超出范围: {idx}")
                                return False
                        except (ValueError, IndexError):
                            print(f"无效的索引: {path_parts[i+1]}")
                            return False
                elif part == "children" and "children" in current_node:
                    if i + 1 < len(path_parts):
                        try:
                            idx = int(path_parts[i+1])
                            if idx < len(current_node["children"]):
                                if i + 1 == len(path_parts) - 1:  # 最后一层
                                    parent_node = current_node["children"]
                                    break
                                current_node = current_node["children"][idx]
                                # 跳过索引
                                i += 1
                            else:
                                print(f"索引超出范围: {idx}")
                                return False
                        except (ValueError, IndexError):
                            print(f"无效的索引: {path_parts[i+1]}")
                            return False
                elif part == "content" and "content" in current_node:
                    if i + 1 < len(path_parts):
                        try:
                            idx = int(path_parts[i+1])
                            if idx < len(current_node["content"]):
                                if i + 1 == len(path_parts) - 1:  # 最后一层
                                    parent_node = current_node["content"]
                                    break
                                current_node = current_node["content"][idx]
                                # 跳过索引
                                i += 1
                            else:
                                print(f"索引超出范围: {idx}")
                                return False
                        except (ValueError, IndexError):
                            print(f"无效的索引: {path_parts[i+1]}")
                            return False
        
        if parent_node is None:
            print(f"无法找到父节点: {'/'.join(parent_path_parts)}")
            return False
        
        # 获取目标节点索引
        try:
            target_index = int(path_parts[-1])
            
            if target_index >= len(parent_node):
                print(f"目标索引超出范围: {target_index}")
                return False
            
            # 执行修复
            if fix_mode == "add_placeholder":
                # 添加占位符内容
                if "type" in parent_node[target_index] and parent_node[target_index]["type"] == "table":
                    if not parent_node[target_index].get("content", "").strip():
                        parent_node[target_index]["content"] = "(表格内容为空)"
                    if not parent_node[target_index].get("caption", "").strip():
                        parent_node[target_index]["caption"] = "空表格"
                    if not parent_node[target_index].get("translated_caption", "").strip():
                        parent_node[target_index]["translated_caption"] = "空表格"
                    
                    print(f"已为表格节点添加占位符内容")
                else:
                    print(f"目标节点不是表格类型，无法添加占位符")
            elif fix_mode == "remove_node":
                # 删除节点
                parent_node.pop(target_index)
                print(f"已删除节点: {node_path}")
            else:
                print(f"不支持的修复模式: {fix_mode}")
                return False
                
            # 保存修改后的RAG树
            backup_file(file_path)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(rag_tree, f, ensure_ascii=False, indent=2)
                
            print(f"成功保存修改后的RAG树")
            return True
            
        except (ValueError, IndexError) as e:
            print(f"处理目标索引时出错: {str(e)}")
            return False
            
    except Exception as e:
        print(f"修复节点失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("RAG处理器修复工具\n")
    print("该工具提供以下功能：")
    print("1. 修补RagProcessor中的_generate_md_content方法")
    print("2. 测试修补后的方法")
    print("3. 为特定节点添加占位符内容")
    print("4. 从树中删除特定节点")
    print("0. 退出")
    
    choice = input("\n请选择要执行的操作 [0-4]: ")
    
    if choice == "1":
        patch_generate_md_content()
    elif choice == "2":
        test_generate_markdown()
    elif choice == "3" or choice == "4":
        # 获取RAG树文件路径
        paper_id = "2023 Cross-modal Contrastive Learning for Multimodal Fake News Detection"
        node_path = "/sections/2/children/3/content/19"  # 从日志中提取的路径
        
        # 尝试从output目录下找到该论文的rag_tree文件
        base_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(base_dir, "output")
        
        # 查找索引文件确定路径
        index_path = os.path.join(output_dir, "papers_index.json")
        file_path = ""
        
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                papers_index = json.load(f)
            
            # 查找指定论文
            paper_info = None
            for paper in papers_index:
                if paper.get('id') == paper_id:
                    paper_info = paper
                    break
            
            if paper_info:
                tree_path = paper_info.get('paths', {}).get('rag_tree', '')
                if tree_path:
                    file_path = os.path.join(output_dir, tree_path)
        
        # 如果没找到，尝试根据目录结构推断
        if not file_path or not os.path.exists(file_path):
            potential_path = os.path.join(output_dir, paper_id, "vectors", f"{paper_id}_tree.json")
            if os.path.exists(potential_path):
                file_path = potential_path
        
        # 如果仍然没找到，让用户输入
        if not file_path or not os.path.exists(file_path):
            print(f"未找到论文 {paper_id} 的RAG树文件")
            file_path = input("请输入RAG树文件的完整路径: ")
            
        # 执行对应操作
        if os.path.exists(file_path):
            if choice == "3":
                fix_mode = "add_placeholder"
            else:
                fix_mode = "remove_node"
                
            fix_node_in_tree(file_path, node_path, fix_mode)
        else:
            print(f"RAG树文件不存在: {file_path}")
    elif choice == "0":
        print("退出程序")
    else:
        print("无效的选择") 