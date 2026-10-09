import json
import logging
from typing import Optional, Dict, Any
import numpy as np
import redis.asyncio as redis
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.query import Query
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("SemanticCache")

class RedisSemanticCache:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=False)
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        self.index_name = "idx:llm_cache"
        self.vector_dim = 384
        
    async def initialize_index(self):
        """Creates an HNSW vector index in Redis if it does not exist."""
        try:
            await self.redis.ft(self.index_name).info()
        except redis.exceptions.ResponseError:
            logger.info("Creating RediSearch HNSW vector index...")
            schema = (
                TextField("prompt"),
                TextField("response_payload"),
                VectorField(
                    "embedding",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.vector_dim,
                        "DISTANCE_METRIC": "COSINE"
                    }
                )
            )
            # Prefix mapping keeps the vector index automatically synced with hash keys
            definition = IndexDefinition(prefix=["autopilot:cache:"], index_type=IndexType.HASH)
            await self.redis.ft(self.index_name).create_index(fields=schema, definition=definition)

    async def get_match(self, prompt: str, threshold: float = 0.92) -> Optional[Dict[str, Any]]:
        """Executes native C-level vector KNN search via Redis dialect 2."""
        embedding = self.encoder.encode(prompt, convert_to_numpy=True).astype(np.float32)
        
        # RediSearch vector query syntax
        query = (
            Query("*=>[KNN 1 @embedding $vec AS score]")
            .sort_by("score")
            .return_fields("response_payload", "score")
            .dialect(2)
        )
        
        res = await self.redis.ft(self.index_name).search(
            query, query_params={"vec": embedding.tobytes()}
        )
        
        if res.docs:
            # Redis COSINE distance is [0, 2]. Similarity = 1 - distance.
            similarity = 1.0 - float(res.docs[0].score)
            if similarity >= threshold:
                logger.info(f"Cache HIT | Similarity: {similarity:.4f}")
                return json.loads(res.docs[0].response_payload)
        return None

    async def set_match(self, prompt: str, payload: Dict[str, Any], ttl_seconds: int = 86400):
        """Asynchronously persists the embedding and payload as a Redis Hash."""
        embedding = self.encoder.encode(prompt, convert_to_numpy=True).astype(np.float32)
        key = f"autopilot:cache:{hash(prompt)}"
        
        mapping = {
            "prompt": prompt,
            "response_payload": json.dumps(payload),
            "embedding": embedding.tobytes()
        }
        await self.redis.hset(key, mapping=mapping)
        await self.redis.expire(key, ttl_seconds)
