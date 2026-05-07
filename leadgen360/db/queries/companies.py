import asyncpg
from uuid import UUID


async def upsert_company(
    conn: asyncpg.Connection,
    name: str,
    linkedin_url: str,
    country: str,
    sector: str,
    source: str,
    raw_data: str,
    website: str | None = None,
    city: str | None = None,
) -> UUID:
    return await conn.fetchval(
        """
        INSERT INTO companies (name, linkedin_url, website, country, city, sector, source, raw_data)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
        ON CONFLICT (linkedin_url) DO UPDATE
            SET name        = EXCLUDED.name,
                sector      = EXCLUDED.sector,
                updated_at  = NOW()
        RETURNING id
        """,
        name, linkedin_url, website, country, city, sector, source, raw_data,
    )


async def get_company_by_id(conn: asyncpg.Connection, company_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT * FROM companies WHERE id = $1",
        company_id,
    )


async def list_companies(conn: asyncpg.Connection, country: str | None = None, limit: int = 100) -> list:
    if country:
        return await conn.fetch(
            "SELECT * FROM companies WHERE country = $1 ORDER BY created_at DESC LIMIT $2",
            country, limit,
        )
    return await conn.fetch(
        "SELECT * FROM companies ORDER BY created_at DESC LIMIT $1",
        limit,
    )
