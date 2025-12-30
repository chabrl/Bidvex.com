"""
BidVex AI Knowledge Base Service
Handles document loading, embedding, and semantic search using ChromaDB
"""

import os
import logging
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import glob

logger = logging.getLogger(__name__)

class KnowledgeBase:
    """Manages the BidVex knowledge base with vector embeddings"""
    
    def __init__(self, openai_api_key: str):
        """Initialize ChromaDB and OpenAI embeddings"""
        self.openai_api_key = openai_api_key
        
        # Initialize ChromaDB with persistent storage
        self.chroma_client = chromadb.Client(Settings(
            persist_directory="./chroma_db",
            anonymized_telemetry=False
        ))
        
        # Initialize OpenAI embedding function
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=openai_api_key,
            model_name="text-embedding-3-small"
        )
        
        # Get or create collection
        try:
            self.collection = self.chroma_client.get_collection(
                name="bidvex_knowledge",
                embedding_function=self.embedding_function
            )
            logger.info(f"Loaded existing knowledge base with {self.collection.count()} documents")
        except:
            self.collection = self.chroma_client.create_collection(
                name="bidvex_knowledge",
                embedding_function=self.embedding_function,
                metadata={"description": "BidVex platform knowledge base"}
            )
            logger.info("Created new knowledge base collection")
            self.load_documents()
    
    def load_documents(self):
        """Load all markdown documents from knowledge_base directory"""
        knowledge_dir = os.path.join(os.path.dirname(__file__), "../knowledge_base")
        
        if not os.path.exists(knowledge_dir):
            logger.warning(f"Knowledge base directory not found: {knowledge_dir}")
            return
        
        md_files = glob.glob(os.path.join(knowledge_dir, "*.md"))
        
        if not md_files:
            logger.warning(f"No markdown files found in {knowledge_dir}")
            return
        
        documents = []
        metadatas = []
        ids = []
        
        for i, file_path in enumerate(md_files):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Split into chunks (by sections marked with ##)
                chunks = self._split_into_chunks(content, file_path)
                
                for j, chunk in enumerate(chunks):
                    doc_id = f"{os.path.basename(file_path)}_{j}"
                    documents.append(chunk['text'])
                    metadatas.append({
                        'source': os.path.basename(file_path),
                        'chunk_id': j,
                        'section': chunk['section']
                    })
                    ids.append(doc_id)
                
                logger.info(f"Loaded {len(chunks)} chunks from {os.path.basename(file_path)}")
            
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
        
        if documents:
            # Add documents to ChromaDB (will generate embeddings automatically)
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Successfully added {len(documents)} document chunks to knowledge base")
    
    def _split_into_chunks(self, content: str, file_path: str) -> List[Dict[str, str]]:
        """Split document into semantic chunks based on headers"""
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_section = "Introduction"
        
        for line in lines:
            # New section on ## header
            if line.startswith('## '):
                if current_chunk:
                    chunks.append({
                        'text': '\n'.join(current_chunk).strip(),
                        'section': current_section
                    })
                current_section = line.replace('##', '').strip()
                current_chunk = [line]
            else:
                current_chunk.append(line)
        
        # Add last chunk
        if current_chunk:
            chunks.append({
                'text': '\n'.join(current_chunk).strip(),
                'section': current_section
            })
        
        # If no sections found, create one large chunk
        if len(chunks) == 0:
            chunks.append({
                'text': content.strip(),
                'section': os.path.basename(file_path)
            })
        
        return chunks
    
    def search(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Search knowledge base for relevant information"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            # Format results
            formatted_results = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    formatted_results.append({
                        'content': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else 0
                    })
            
            return formatted_results
        
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return []
    
    def get_all_documents(self) -> int:
        """Get total count of documents in knowledge base"""
        return self.collection.count()
    
    def clear_and_reload(self):
        """Clear knowledge base and reload all documents"""
        try:
            self.chroma_client.delete_collection(name="bidvex_knowledge")
            logger.info("Cleared existing knowledge base")
            self.__init__(self.openai_api_key)
        except Exception as e:
            logger.error(f"Error clearing knowledge base: {e}")


# Singleton instance
_knowledge_base = None

def get_knowledge_base(openai_api_key: str) -> KnowledgeBase:
    """Get or create knowledge base singleton"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase(openai_api_key)
    return _knowledge_base
