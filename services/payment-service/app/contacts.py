"""Carnet de contacts (association réflexive ÊTRE_CONTACT), RG-18."""

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import iso_utc, utcnow
from app.errors import api_error
from app.models import Client, Contact
from app.payments import find_by_contact, get_client, parse_contact_or_fail
from app.schemas import ContactIn, ContactOut


def contact_out(link: Contact, display_name: str) -> ContactOut:
    return ContactOut(
        contact_id=link.contact_id,
        display_name=display_name,
        alias=link.alias,
        added_at=iso_utc(link.added_at),
    )


async def list_contacts(session: AsyncSession, client_id: str) -> list[ContactOut]:
    rows = (
        await session.execute(
            select(Contact, Client.display_name)
            .join(Client, Client.id == Contact.contact_id)
            .where(Contact.owner_id == client_id)
            .order_by(func.coalesce(Contact.alias, Client.display_name))
        )
    ).all()
    return [contact_out(link, name) for link, name in rows]


async def add_contact(state, session: AsyncSession, client_id: str, body: ContactIn) -> ContactOut:
    me = await get_client(session, client_id)
    found = await find_by_contact(session, parse_contact_or_fail(body.contact), me)
    if found is None:
        # Seuls les clients Orbe peuvent être ajoutés ; la limitation de débit freine
        # l'énumération des comptes
        raise api_error(404, "contact_not_found", "Aucun compte Orbe ne correspond à ce contact.")
    if found.id == me.id:
        raise api_error(422, "self_contact", "Vous ne pouvez pas vous ajouter vous-même.")
    count = await session.scalar(
        select(func.count()).select_from(Contact).where(Contact.owner_id == me.id)
    )
    if count >= state.settings.max_contacts:
        raise api_error(422, "too_many_contacts", "Nombre maximal de contacts atteint.")
    link = Contact(owner_id=me.id, contact_id=found.id, alias=body.alias, added_at=utcnow())
    session.add(link)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise api_error(409, "contact_exists", "Ce contact est déjà dans votre carnet.") from None
    return contact_out(link, found.display_name)


async def remove_contact(session: AsyncSession, client_id: str, contact_id: str) -> None:
    result = await session.execute(
        delete(Contact).where(Contact.owner_id == client_id, Contact.contact_id == contact_id)
    )
    await session.commit()
    if result.rowcount != 1:
        raise api_error(404, "contact_not_found", "Contact introuvable.")
