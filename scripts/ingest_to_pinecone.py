"""
Pinecone Data Ingestion Pipeline for InsureGPT.
Chunks policy documents, generates 1024-d embeddings via Pinecone Inference (multilingual-e5-large),
and batch upserts vectors into the Pinecone index.
"""
import os
import re
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Dict, Any
from app.config import get_settings
from pinecone import Pinecone

settings = get_settings()


def load_documents(docs_dir: str = "data/documents") -> List[Dict[str, Any]]:
    """Load raw text documents from data/documents."""
    documents = []
    if not os.path.exists(docs_dir):
        print(f"[ERROR] Directory '{docs_dir}' does not exist.")
        return []

    for fname in sorted(os.listdir(docs_dir)):
        if fname.endswith(".txt"):
            fpath = os.path.join(docs_dir, fname)
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Extract Policy ID if present
            policy_id_match = re.search(r"Policy Document ID:\s*([A-Z0-9\-]+)|Document ID:\s*([A-Z0-9\-]+)", content)
            policy_id = policy_id_match.group(1) or policy_id_match.group(2) if policy_id_match else fname.replace(".txt", "")

            documents.append({
                "filename": fname,
                "policy_id": policy_id,
                "text": content
            })

    print(f"[INFO] Loaded {len(documents)} documents from '{docs_dir}'.")
    return documents


def chunk_document(doc: Dict[str, Any], max_chunk_chars: int = 1200) -> List[Dict[str, Any]]:
    """
    Split document text into structural sections and clauses without truncating hyphenated titles.
    """
    raw_text = doc["text"]
    filename = doc["filename"]
    policy_id = doc["policy_id"]

    # Split cleanly by lines starting with SECTION <number>
    section_splits = re.split(r"(?m)^(SECTION\s+\d+[^\r\n]*)", raw_text)
    chunks = []
    current_section = "General Overview"

    i = 0
    while i < len(section_splits):
        part = section_splits[i].strip()
        if not part:
            i += 1
            continue

        if part.startswith("SECTION"):
            current_section = part
            if i + 1 < len(section_splits):
                body = section_splits[i + 1].strip()
                # Clean leading and trailing divider lines
                body = re.sub(r"^[-=]{5,}\s*", "", body)
                body = re.sub(r"\s*[-=]{5,}$", "", body)
                i += 2
            else:
                body = ""
                i += 1
        else:
            body = part
            body = re.sub(r"^[-=]{5,}\s*", "", body)
            body = re.sub(r"\s*[-=]{5,}$", "", body)
            i += 1

        if not body:
            continue

        # Split body by sub-clauses (e.g. 1.1, 2.1, or numbered points like 1. Claim Form:)
        subparts = [p.strip() for p in re.split(r"(?m)^(?=\d+\.\d+|\d+\.\s+[A-Z])", body) if p.strip()]
        if not subparts:
            subparts = [body]

        for sub in subparts:
            sub = re.sub(r"^[-=]{5,}\s*", "", sub).strip()
            sub = re.sub(r"\s*[-=]{5,}$", "", sub).strip()
            if not sub:
                continue

            # If still exceeds max chars, split by paragraphs
            if len(sub) > max_chunk_chars:
                paragraphs = [p.strip() for p in sub.split("\n\n") if p.strip()]
                buf = ""
                for p in paragraphs:
                    if len(buf) + len(p) + 2 < max_chunk_chars:
                        buf += ("\n\n" + p) if buf else p
                    else:
                        if buf and len(buf) > 40:
                            chunks.append({
                                "text": buf.strip(),
                                "section": current_section,
                                "filename": filename,
                                "policy_id": policy_id
                            })
                        buf = p
                if buf and len(buf) > 40:
                    chunks.append({
                        "text": buf.strip(),
                        "section": current_section,
                        "filename": filename,
                        "policy_id": policy_id
                    })
            else:
                if len(sub) > 40:
                    chunks.append({
                        "text": sub,
                        "section": current_section,
                        "filename": filename,
                        "policy_id": policy_id
                    })

    return chunks


def ingest_to_pinecone(index_name: str = "insuregpt-index", namespace: str = "default"):
    """Main ingestion runner."""
    api_key = settings.pinecone_api_key
    if not api_key or api_key == "dummy_key":
        print("[ERROR] Valid PINECONE_API_KEY is not configured in .env.")
        sys.exit(1)

    print(f"[INFO] Initializing Pinecone client...")
    pc = Pinecone(api_key=api_key)

    # Check index
    index_list = [i.name for i in pc.list_indexes()]
    if index_name not in index_list:
        print(f"[ERROR] Index '{index_name}' not found. Available indexes: {index_list}")
        sys.exit(1)

    index = pc.Index(index_name)
    print(f"[INFO] Connected to Pinecone index: '{index_name}'.")

    # Clear previous stale chunks in the namespace if any
    try:
        index.delete(delete_all=True, namespace=namespace)
        print(f"[INFO] Cleared previous namespace '{namespace}' in '{index_name}'.")
    except Exception as e:
        print(f"[INFO] Namespace wipe notice (expected if empty): {e}")

    # Load and chunk docs
    docs = load_documents()
    all_chunks = []
    for doc in docs:
        doc_chunks = chunk_document(doc)
        print(f"  - {doc['filename']}: generated {len(doc_chunks)} chunks.")
        all_chunks.extend(doc_chunks)

    print(f"[INFO] Total chunks across all policy documents: {len(all_chunks)}")

    # Batch embedding and upserting
    batch_size = 32
    total_upserted = 0

    print(f"[INFO] Generating embeddings with model 'multilingual-e5-large' and upserting in batches of {batch_size}...")

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        texts = [c["text"] for c in batch]

        try:
            # Generate embeddings via native Pinecone Inference
            embeddings = pc.inference.embed(
                model="multilingual-e5-large",
                inputs=texts,
                parameters={"input_type": "passage", "truncate": "END"}
            )

            vectors_to_upsert = []
            for j, (chunk, emb) in enumerate(zip(batch, embeddings)):
                vec_id = f"{chunk['policy_id']}#chunk_{i + j:04d}"
                vectors_to_upsert.append({
                    "id": vec_id,
                    "values": emb.values,
                    "metadata": {
                        "policy_id": chunk["policy_id"],
                        "filename": chunk["filename"],
                        "section": chunk["section"][:200],
                        "text": chunk["text"][:2000]  # Store text payload for direct retrieval
                    }
                })

            index.upsert(vectors=vectors_to_upsert, namespace=namespace)
            total_upserted += len(vectors_to_upsert)
            print(f"  [Progress] Upserted {total_upserted}/{len(all_chunks)} vectors...")
            time.sleep(0.2)

        except Exception as e:
            print(f"[ERROR] Batch upsert error at index {i}: {e}")

    print("\n" + "=" * 60)
    print(f"SUCCESS! Successfully ingested {total_upserted} vectors into Pinecone!")
    print(f"Index: {index_name} | Namespace: {namespace}")
    stats = index.describe_index_stats()
    print(f"Index Stats: Total Vectors = {stats.total_vector_count}")
    print("=" * 60)


if __name__ == "__main__":
    ingest_to_pinecone()
