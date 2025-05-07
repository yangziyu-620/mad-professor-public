import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# 文件已移动到utils/rebuild_faiss.py
import json
import sys
from pathlib import Path
from processor.rag_processor import RagProcessor

def list_papers(output_dir):
    """
    列出可用的论文列表
    
    Args:
        output_dir: 输出目录路径
        
    Returns:
        论文ID列表和索引数据
    """
    # 查找索引文件
    index_path = os.path.join(output_dir, "papers_index.json")
    paper_list = []
    
    if os.path.exists(index_path):
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                papers_index = json.load(f)
                
            for i, paper in enumerate(papers_index):
                paper_id = paper.get('id', '')
                paper_list.append((i+1, paper_id))
                
            return paper_list, papers_index
            
        except Exception as e:
            print(f"加载论文索引失败: {str(e)}")
            return [], []
    else:
        print(f"论文索引文件不存在: {index_path}")
        return [], []

def check_vector_store(paper_id, paper_dir):
    """
    检查向量库状态
    
    Args:
        paper_id: 论文ID
        paper_dir: 论文目录
        
    Returns:
        向量库状态信息
    """
    vector_dir = paper_dir / "vectors"
    
    if not vector_dir.exists():
        return "向量库目录不存在"
    
    index_faiss = vector_dir / "index.faiss"
    index_pkl = vector_dir / "index.pkl"
    
    if not index_faiss.exists() or not index_pkl.exists():
        existing_files = []
        if index_faiss.exists():
            existing_files.append("index.faiss")
        if index_pkl.exists():
            existing_files.append("index.pkl")
            
        if existing_files:
            return f"向量库不完整，仅存在: {', '.join(existing_files)}"
        else:
            return "向量库索引文件不存在"
    
    # 检查文件大小是否正常
    faiss_size = index_faiss.stat().st_size
    pkl_size = index_pkl.stat().st_size
    
    if faiss_size < 1000:  # 小于1KB可能有问题
        return f"index.faiss文件异常 (大小: {faiss_size} 字节)"
    
    if pkl_size < 100:  # 小于100字节可能有问题
        return f"index.pkl文件异常 (大小: {pkl_size} 字节)"
        
    return f"正常 (index.faiss: {format_size(faiss_size)}, index.pkl: {format_size(pkl_size)})"

def format_size(size):
    """格式化文件大小显示"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def rebuild_faiss_index(paper_id, output_dir, force=False):
    """
    重建特定论文的Faiss索引
    
    Args:
        paper_id: 论文ID
        output_dir: 输出目录
        force: 是否强制重建，即使索引看起来正常
        
    Returns:
        bool: 重建成功返回True，否则返回False
    """
    paper_dir = Path(output_dir) / paper_id
    
    if not paper_dir.exists():
        print(f"论文目录不存在: {paper_dir}")
        return False
        
    # 检查当前向量库状态
    status = check_vector_store(paper_id, paper_dir)
    print(f"当前向量库状态: {status}")
    
    if "正常" in status and not force:
        choice = input("向量库似乎正常，是否仍要重建? (y/n): ").lower()
        if choice != 'y':
            print("取消重建")
            return False
    
    # 初始化RAG处理器
    processor = RagProcessor()
    
    # 调用重建方法
    print(f"开始重建 {paper_id} 的向量库...")
    result = processor.rebuild_vector_store(paper_id, paper_dir)
    
    if result:
        print(f"成功重建向量库: {paper_id}")
        
        # 重新检查状态
        new_status = check_vector_store(paper_id, paper_dir)
        print(f"重建后向量库状态: {new_status}")
        return True
    else:
        print(f"重建向量库失败: {paper_id}")
        return False

def scan_papers_with_issues(output_dir):
    """
    扫描并识别所有存在向量库问题的论文
    
    Args:
        output_dir: 输出目录
        
    Returns:
        问题论文列表
    """
    paper_list, papers_index = list_papers(output_dir)
    problematic_papers = []
    
    print("\n正在扫描所有论文的向量库状态...")
    for i, paper_id in paper_list:
        paper_dir = Path(output_dir) / paper_id
        if paper_dir.exists():
            status = check_vector_store(paper_id, paper_dir)
            if "正常" not in status:
                problematic_papers.append((paper_id, status))
                print(f"发现问题: {paper_id} - {status}")
    
    return problematic_papers

def batch_rebuild(problematic_papers, output_dir):
    """
    批量重建所有问题论文的向量库
    
    Args:
        problematic_papers: 问题论文列表
        output_dir: 输出目录
        
    Returns:
        成功重建的论文数量
    """
    success_count = 0
    total = len(problematic_papers)
    
    print(f"\n开始批量重建 {total} 篇论文的向量库...")
    
    for i, (paper_id, status) in enumerate(problematic_papers):
        print(f"\n处理 [{i+1}/{total}] {paper_id}")
        print(f"当前状态: {status}")
        
        if rebuild_faiss_index(paper_id, output_dir, force=True):
            success_count += 1
    
    print(f"\n批量重建完成，成功: {success_count}/{total}")
    return success_count

def main():
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(base_dir, "output")
    
    if not os.path.exists(output_dir):
        print(f"输出目录不存在: {output_dir}")
        sys.exit(1)
    
    print("Faiss 索引重建工具")
    print("==================\n")
    print("该工具用于重建论文的Faiss向量索引文件 (index.faiss 和 index.pkl)")
    print(f"数据目录: {output_dir}\n")
    
    print("可用选项:")
    print("1. 选择特定论文重建索引")
    print("2. 扫描并列出所有存在问题的论文")
    print("3. 批量重建所有存在问题的论文")
    print("0. 退出")
    
    choice = input("\n请选择操作 [0-3]: ")
    
    if choice == "1":
        # 列出所有论文
        paper_list, papers_index = list_papers(output_dir)
        
        if not paper_list:
            print("未找到任何论文，请检查索引文件")
            sys.exit(1)
            
        print("\n可用论文列表:")
        for i, paper_id in paper_list:
            print(f"{i}. {paper_id}")
            
        paper_choice = input("\n请选择论文序号，或直接输入论文ID: ")
        
        selected_paper_id = None
        if paper_choice.isdigit() and 1 <= int(paper_choice) <= len(paper_list):
            selected_paper_id = paper_list[int(paper_choice)-1][1]
        else:
            # 检查是否是有效的论文ID
            if any(paper_id == paper_choice for _, paper_id in paper_list):
                selected_paper_id = paper_choice
        
        if selected_paper_id:
            rebuild_faiss_index(selected_paper_id, output_dir)
        else:
            print("无效的选择")
            
    elif choice == "2":
        problematic_papers = scan_papers_with_issues(output_dir)
        
        if problematic_papers:
            print("\n发现以下存在问题的论文:")
            for i, (paper_id, status) in enumerate(problematic_papers):
                print(f"{i+1}. {paper_id} - {status}")
        else:
            print("\n未发现任何存在问题的论文")
    
    elif choice == "3":
        problematic_papers = scan_papers_with_issues(output_dir)
        
        if problematic_papers:
            print(f"\n发现 {len(problematic_papers)} 篇存在问题的论文")
            confirm = input("是否批量重建所有存在问题的论文? (y/n): ").lower()
            
            if confirm == 'y':
                batch_rebuild(problematic_papers, output_dir)
            else:
                print("已取消批量重建")
        else:
            print("\n未发现任何存在问题的论文，无需批量重建")
    
    elif choice == "0":
        print("退出程序")
    else:
        print("无效的选择")

if __name__ == "__main__":
    main() 