import asyncpg
from uuid import UUID


async def upsert_contact(
    conn: asyncpg.Connection,
    company_id: UUID,
    full_name: str,
    job_title: str,
    linkedin_url: str,
    email: str | None = None,
    is_decision_maker: bool = False,
    source: str = "linkedin",
) -> UUID:
    return await conn.fetchval(
        """
        INSERT INTO contacts (company_id, full_name, job_title, email, linkedin_url, is_decision_maker, source)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (linkedin_url) DO UPDATE
            SET full_name        = EXCLUDED.full_name,
                job_title        = EXCLUDED.job_title,
                email            = COALESCE(EXCLUDED.email, contacts.email),
                is_decision_maker = EXCLUDED.is_decision_maker
        RETURNING id
        """,
        company_id, full_name, job_title, email, linkedin_url, is_decision_maker, source,
    )


async def get_contact_by_id(conn: asyncpg.Connection, contact_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM contacts WHERE id = $1", contact_id)


async def get_contacts_for_company(conn: asyncpg.Connection, company_id: UUID) -> list:
    return await conn.fetch(
        "SELECT * FROM contacts WHERE company_id = $1 ORDER BY is_decision_maker DESC",
        company_id,
    )
