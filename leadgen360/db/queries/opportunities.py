import asyncpg
from uuid import UUID


async def insert_opportunity(
    conn: asyncpg.Connection,
    company_id: UUID,
    title: str,
    description: str,
    opportunity_type: str,
    technologies: list[str],
    source_url: str,
    source_platform: str,
    country: str,
    priority_score: int,
    sector_label: str,
) -> UUID:
    return await conn.fetchval(
        """
        INSERT INTO opportunities (
            company_id, title, description, opportunity_type, technologies,
            source_url, source_platform, country, priority_score, sector_label, status
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'new')
        RETURNING id
        """,
        company_id, title, description, opportunity_type, technologies,
        source_url, source_platform, country, priority_score, sector_label,
    )


async def check_duplicate(
    conn: asyncpg.Connection,
    company_id: UUID,
    technology: str,
) -> bool:
    row = await conn.fetchval(
        """
        SELECT id FROM opportunities
        WHERE company_id = $1
          AND $2 = ANY(technologies)
          AND opportunity_type = 'hiring_signal'
          AND created_at > NOW() - INTERVAL '30 days'
        """,
        company_id, technology,
    )
    return row is not None


async def update_nlp_labels(
    conn: asyncpg.Connection,
    opportunity_id: UUID,
    sector_label: str,
    tech_label: str,
    priority_label: str,
    nlp_confidence: float,
    priority_score: int,
) -> None:
    await conn.execute(
        """
        UPDATE opportunities
        SET sector_label    = $2,
            tech_label      = $3,
            priority_label  = $4,
            nlp_confidence  = $5,
            priority_score  = $6,
            updated_at      = NOW()
        WHERE id = $1
        """,
        opportunity_id, sector_label, tech_label, priority_label, nlp_confidence, priority_score,
    )


async def get_top_opportunities(
    conn: asyncpg.Connection,
    min_score: int = 0,
    country: str | None = None,
    limit: int = 20,
) -> list:
    if country:
        return await conn.fetch(
            """
            SELECT o.*, c.name as company_name, c.linkedin_url as company_linkedin
            FROM opportunities o
            JOIN companies c ON c.id = o.company_id
            WHERE o.priority_score >= $1 AND o.country = $2
            ORDER BY o.priority_score DESC, o.created_at DESC
            LIMIT $3
            """,
            min_score, country, limit,
        )
    return await conn.fetch(
        """
        SELECT o.*, c.name as company_name, c.linkedin_url as company_linkedin
        FROM opportunities o
        JOIN companies c ON c.id = o.company_id
        WHERE o.priority_score >= $1
        ORDER BY o.priority_score DESC, o.created_at DESC
        LIMIT $2
        """,
        min_score, limit,
    )


async def get_opportunity_by_id(conn: asyncpg.Connection, opp_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT o.*, c.name as company_name, c.linkedin_url as company_linkedin,
               c.country as company_country, c.sector as company_sector
        FROM opportunities o
        JOIN companies c ON c.id = o.company_id
        WHERE o.id = $1
        """,
        opp_id,
    )
