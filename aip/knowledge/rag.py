"""简单知识库检索 - 支撑知识问答演示."""

from __future__ import annotations

from pathlib import Path


class KnowledgeEngine:
  """基于关键词匹配的知识检索（MVP），生产环境替换为向量 RAG。"""

  def __init__(self, knowledge_dir: str | Path):
    self.knowledge_dir = Path(knowledge_dir)
    self._docs: list[dict[str, str]] = []
    self._load()

  def _load(self) -> None:
    for path in self.knowledge_dir.glob("*.md"):
      self._docs.append({"id": path.stem, "title": path.stem, "content": path.read_text(encoding="utf-8")})

  def search(self, question: str, top_k: int = 3) -> list[dict[str, str]]:
    keywords = [w for w in question.replace("？", "").replace("?", "").split() if len(w) >= 2]
    scored = []
    for doc in self._docs:
      score = sum(1 for kw in keywords if kw in doc["content"] or kw in doc["title"])
      # 子串匹配
      for kw in ["CRR", "销贷比", "科创", "绿色", "贷前", "贷后", "操作", "政策", "产品"]:
        if kw in question and kw in doc["content"]:
          score += 2
      if score > 0:
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"id": d["id"], "title": d["title"], "snippet": d["content"][:500], "score": s} for s, d in scored[:top_k]]

  def answer(self, question: str) -> dict:
    hits = self.search(question)
    if not hits:
      return {"type": "knowledge", "found": False, "answer": "未找到相关知识，请换个问法或联系管理员。"}
    best = hits[0]
    return {
      "type": "knowledge",
      "found": True,
      "answer": f"根据《{best['title']}》：\n{best['snippet'][:300]}...",
      "sources": [{"id": h["id"], "title": h["title"]} for h in hits],
      "evidence": [{"type": "knowledge", "source": best["id"], "detail": best["title"]}],
    }
