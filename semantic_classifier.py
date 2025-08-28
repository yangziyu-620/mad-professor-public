from __future__ import annotations
"""semantic_classifier.py

轻量级语义分类器，用于根据论文标题/摘要与类别描述的语义相似度确定最佳类别。

设计目标：
1. **最少依赖**：仅依赖 sentence-transformers（自动带入 transformers & torch）。
2. **缓存模型和类别向量**：首次调用后常驻内存，加速后续分类。
3. **兼容 DataManager**：暴露 `get_best_category` 函数，便于在 `_classify_paper_field` 中调用。

推荐模型：`paraphrase-multilingual-MiniLM-L12-v2` —— 体积小、支持中英混合。

用法示例：
```
from semantic_classifier import get_best_category
best_cat, score = get_best_category(text, field_keywords)
```
"""

from typing import Dict, List, Tuple, Union
from functools import lru_cache

try:
    from sentence_transformers import SentenceTransformer, util  # type: ignore
except ImportError as e:
    raise ImportError("Please install sentence-transformers: pip install -U sentence-transformers") from e

_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_model: Union[SentenceTransformer, None] = None  # 全局模型缓存
_category_cache: Dict[str, Dict[str, List[float]]] = {}  # {cache_key: {cat: emb}}


def _load_model() -> SentenceTransformer:
    """懒加载 SentenceTransformer 模型，避免启动时卡顿。"""
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
        _model.max_seq_length = 256  # 限制长度，加速推理
    return _model


def _build_category_descriptions(field_keywords: Dict[str, List[str]]) -> Dict[str, str]:
    """把关键词列表拼接为类别描述字符串。"""
    descriptions = {
        cat: (
            cat  # 类别名称本身
            + ": "
            + ", ".join(keywords[:30])  # 截取前30个关键词，避免描述过长
        )
        for cat, keywords in field_keywords.items()
    }
    return descriptions


def _get_category_embeddings(descriptions: Dict[str, str]) -> Dict[str, List[float]]:
    key = "||".join(f"{k}:{v}" for k, v in sorted(descriptions.items()))
    if key in _category_cache:
        return _category_cache[key]
    model = _load_model()
    vectors = model.encode(list(descriptions.values()), normalize_embeddings=True)
    embs = {cat: vec for cat, vec in zip(descriptions.keys(), vectors)}
    _category_cache[key] = embs
    return embs


def get_best_category(
    text: str,
    field_keywords: Dict[str, List[str]],
    threshold: float = 0.35,
) -> Tuple[str, float]:
    """根据语义相似度返回最佳类别及得分。

    Args:
        text: 待分类文本（标题+摘要等）
        field_keywords: 类别到关键词列表的映射
        threshold: 置信度阈值，低于此阈值可认为分类不确定

    Returns:
        (best_category, best_score)
    """
    if not text.strip():
        return "其他", 0.0

    descriptions = _build_category_descriptions(field_keywords)
    cat_embs = _get_category_embeddings(descriptions)
    model = _load_model()

    # 编码文本
    text_emb = model.encode(text, normalize_embeddings=True)

    # 计算相似度
    best_cat = "其他"
    best_score = -1.0
    for cat, emb in cat_embs.items():
        score = float(util.dot_score(text_emb, emb))
        if score > best_score:
            best_cat, best_score = cat, score

    # 如果最佳得分都低于阈值，则返回"其他"
    if best_score < threshold:
        return "其他", best_score
    return best_cat, best_score 