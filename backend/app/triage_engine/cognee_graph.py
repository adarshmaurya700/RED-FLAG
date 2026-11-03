import hashlib
import json
import networkx as nx
from sqlalchemy import select
from app.models.database import Product, GraphEdge, CaseFile


async def persist_product_edges(session, product: Product):
    for source, target, relation in [
        (f"brand:{product.brand}", f"product:{product.id}", "markets"),
        (f"product:{product.id}", f"case:{product.case_id}", "investigated_in"),
    ]:
        await _edge(session, source, target, relation)
    if product.manufacturing_fssai_license_no:
        await _edge(
            session,
            f"product:{product.id}",
            f"facility:{product.manufacturing_fssai_license_no}",
            "manufactured_at",
        )
    if product.supplier_id:
        await _edge(
            session,
            f"product:{product.id}",
            f"supplier:{product.supplier_id}",
            "supplied_by",
        )


async def _edge(session, source, target, relation):
    identifier = hashlib.sha256(f"{source}|{target}|{relation}".encode()).hexdigest()[
        :32
    ]
    if not await session.get(GraphEdge, identifier):
        session.add(
            GraphEdge(
                id=identifier, source=source, target=target, relation=relation, data={}
            )
        )


async def graph_view(session, case_id: str) -> dict:
    edges = (await session.scalars(select(GraphEdge))).all()
    graph = nx.DiGraph()
    for edge in edges:
        graph.add_edge(edge.source, edge.target, relation=edge.relation)
    root = f"case:{case_id}"
    if root not in graph:
        return {"nodes": [], "edges": [], "facility_alerts": [], "backend": "networkx"}
    members = nx.node_connected_component(graph.to_undirected(), root)
    products = (await session.scalars(select(Product))).all()
    names = {f"product:{p.id}": p.name for p in products}
    nodes = []
    alerts = []
    for identifier in sorted(members):
        kind, label = identifier.split(":", 1)
        nodes.append(
            {
                "id": identifier,
                "label": names.get(identifier, label),
                "kind": kind,
                "license": label if kind == "facility" else None,
            }
        )
        if kind == "facility":
            linked = [p for p in products if p.manufacturing_fssai_license_no == label]
            brands = sorted({p.brand for p in linked})
            if len(brands) > 1:
                alerts.append(
                    {
                        "license": label,
                        "brands": brands,
                        "case_ids": sorted({p.case_id for p in linked}),
                        "status": "cross_brand_review",
                        "message": f"{len(brands)} brands share this manufacturing license. Review facility-level signals.",
                    }
                )
    return {
        "nodes": nodes,
        "edges": [
            {
                "id": edge.id,
                "source": edge.source,
                "target": edge.target,
                "label": edge.relation,
            }
            for edge in edges
            if edge.source in members and edge.target in members
        ],
        "facility_alerts": alerts,
        "backend": "networkx",
        "persistence": "postgresql/sqlalchemy",
    }


async def sync_cognee(graph: dict):
    import cognee

    await cognee.add(json.dumps(graph, ensure_ascii=False))
    await cognee.cognify()
