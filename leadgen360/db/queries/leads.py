import asyncpg
from uuid import UUID


async def create_lead(
    conn: asyncpg.Connection,
    opportunity_id: UUID,
    contact_id: UUID | None,
    linkedin_msg: str,
    email_msg: str | None = None,
) -> UUID:
    return await conn.fetchval(
        """
        INSERT INTO leads (opportunity_id, contact_id, generated_linkedin_msg, generated_email, status)
        VALUES ($1, $2, $3, $4, 'draft')
        RETURNING id
        """,
        opportunity_id, contact_id, linkedin_msg, email_msg,
    )


async def get_lead_by_id(conn: asyncpg.Connection, lead_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT l.*, o.title as opportunity_title, c.full_name as contact_name
        FROM leads l
        LEFT JOIN opportunities o ON o.id = l.opportunity_id
        LEFT JOIN contacts c ON c.id = l.contact_id
        WHERE l.id = $1
        """,
        lead_id,
    )


async def update_lead_status(
    conn: asyncpg.Connection,
    lead_id: UUID,
    status: str,
) -> None:
    await conn.execute(
        "UPDATE leads SET status = $2 WHERE id = $1",
        lead_id, status,
    )
