import os
import datetime
import uuid
import re

try:
    import chromadb
except ImportError:
    chromadb = None

class MemoryManager:
    """Handles the RAG Vector Database and PARA Semantic Markdown storage."""
    def __init__(self, base_path="sunflower/brain"):
        self.base_path = base_path
        self.db_path = os.path.join(base_path, "vector_db")
        self.client = None
        self.collection = None
        
        # Ensure PARA structure exists
        for category in ["projects", "areas", "resources", "archives"]:
            os.makedirs(os.path.join(self.base_path, category), exist_ok=True)
            
        if chromadb:
            try:
                self.client = chromadb.PersistentClient(path=self.db_path)
                self.collection = self.client.get_or_create_collection(name="sunflower_brain")
            except Exception as e:
                print(f"[MemoryManager] ChromaDB init error: {e}")

    def _slugify(self, title: str) -> str:
        return re.sub(r'[\W_]+', '-', title.lower()).strip('-')

    async def save_memory(self, user_id: int, topic: str, content: str, category: str = "resources") -> str:
        """Saves a fact to both the Markdown structure and the Vector DB."""
        if category not in ["projects", "areas", "resources", "archives"]:
            category = "resources"
            
        slug = self._slugify(topic)
        file_path = os.path.join(self.base_path, category, f"{slug}.md")
        
        # 1. Save to Markdown (The Second Brain)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# {topic}\n")
            f.write(f"**Last Updated:** {timestamp}\n")
            f.write(f"**Category:** {category.capitalize()}\n\n")
            f.write(content)
            
        # 2. Save to Vector DB
        if self.collection:
            doc_id = f"U{user_id}_{slug}"
            try:
                # Upsert updates if present or creates new
                self.collection.upsert(
                    documents=[content],
                    metadatas=[{"topic": topic, "category": category, "user_id": user_id, "timestamp": timestamp}],
                    ids=[doc_id]
                )
            except Exception as e:
                print(f"[MemoryManager] Failed to embed to Chroma: {e}")
                
        return f"✅ Memory saved to `{category}/{slug}.md` and embedded in Vector DB."

    async def search_memory(self, user_id: int, query: str, top_k: int = 3) -> str:
        """Searches the Vector DB for semantic matches associated with the user."""
        if not self.collection:
            return ""
            
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where={"user_id": user_id}
            )
            
            if not results or not results['documents'] or not results['documents'][0]:
                return ""
                
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            
            context_blocks = []
            for doc, meta in zip(docs, metas):
                topic = meta.get("topic", "Unknown")
                cat = meta.get("category", "resources")
                context_blocks.append(f"[{cat.upper()} | {topic}]: {doc}")
                
            if context_blocks:
                header = "🧠 **RELEVANT LTM (Long-Term Memory) CONTEXT:**\n"
                return header + "\n".join(context_blocks)
        except Exception as e:
            print(f"[MemoryManager] Search error: {e}")
        return ""
