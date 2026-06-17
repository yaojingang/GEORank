"""
知识图谱服务 — Neo4j
负责公司实体关系的存储与查询
"""
from neo4j import AsyncGraphDatabase
from app.core.config import settings

_driver = AsyncGraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
)


async def create_company_node(company_id: str, properties: dict):
    """创建公司节点"""
    async with _driver.session() as session:
        await session.run(
            """
            MERGE (c:Company {id: $id})
            SET c += $props
            """,
            id=company_id,
            props=properties,
        )


async def add_entities_and_relations(company_id: str, entities: list[dict], relations: list[dict]):
    """
    将 LLM 抽取的实体和关系写入知识图谱
    entities: [{"name": "...", "type": "Product|Person|Technology", "props": {...}}]
    relations: [{"from": "...", "to": "...", "type": "HAS_PRODUCT|FOUNDED_BY|USES_TECH"}]
    """
    async with _driver.session() as session:
        for entity in entities:
            await session.run(
                f"""
                MERGE (e:{entity['type']} {{name: $name}})
                SET e += $props
                MERGE (c:Company {{id: $company_id}})
                MERGE (c)-[:HAS_ENTITY]->(e)
                """,
                name=entity["name"],
                props=entity.get("props", {}),
                company_id=company_id,
            )

        for rel in relations:
            await session.run(
                f"""
                MATCH (a {{name: $from_name}})
                MATCH (b {{name: $to_name}})
                MERGE (a)-[:{rel['type']}]->(b)
                """,
                from_name=rel["from"],
                to_name=rel["to"],
            )


async def get_company_graph(company_id: str) -> dict:
    """获取某公司的完整知识图谱（节点 + 关系）"""
    async with _driver.session() as session:
        result = await session.run(
            """
            MATCH (c:Company {id: $id})-[*1..2]-(n)
            RETURN c, n
            LIMIT 100
            """,
            id=company_id,
        )
        records = [r async for r in result]
        return {"nodes": len(records), "raw": str(records)}
