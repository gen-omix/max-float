"""`python -m max_float.graph.admin` looks after parties by the address that made them.

    find NAME        the parties with an applicant whose name contains NAME
    show ADDRESS     the parties an address made in the last week
    reset ADDRESS    let an address make its week's parties again, keeping them
    clear ADDRESS    delete the parties an address made in the last week

The graph holds an address only as a hash, for a week, so `find` shows hashes, and
ADDRESS is an IP or one of those hashes. It needs the service's `MAX_FLOAT_SECRET`,
as an IP's hash depends on it.
"""

import argparse
from collections.abc import Callable, Sequence

from max_float.graph import driver, party


def lines(found: list[party.Made]) -> list[str]:
    """A line for each party: when it was made, the hash of the address that made
    it, whether it's locked in, and its applicants."""
    return [
        "  ".join(
            [
                f"{each.created:%Y-%m-%d %H:%M}",
                each.ip_hash or "address forgotten".ljust(64),
                "locked in" if each.locked else "planning ",
                ", ".join(each.applicants) or "no applicants",
            ]
        )
        for each in found
    ] or ["No parties."]


def run(
    arguments: Sequence[str] | None = None,
    confirm: Callable[[str], str] = input,
) -> list[str]:
    """Do what the arguments ask and return what to print."""
    parser = argparse.ArgumentParser(prog="python -m max_float.graph.admin")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("find").add_argument("name")
    for name in ("show", "reset", "clear"):
        commands.add_parser(name).add_argument("address")
    asked = parser.parse_args(arguments)
    with driver() as connection, connection.session() as session:
        if asked.command == "find":
            return lines(party.named(session, asked.name))
        found = party.made_by(session, asked.address)
        if asked.command == "show" or not found:
            return lines(found)
        if asked.command == "reset":
            count = party.forget_ip(session, asked.address)
            return [f"{count} parties kept. The address can make parties again."]
        answer = confirm(
            "\n".join([*lines(found), f"Delete these {len(found)}? [y/N] "])
        )
        if answer.strip().lower() != "y":
            return ["Nothing deleted."]
        return [f"{party.remove_ip(session, asked.address)} parties deleted."]


if __name__ == "__main__":
    print("\n".join(run()))
