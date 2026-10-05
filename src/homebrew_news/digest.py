import dataclasses
import re
import typing

if typing.TYPE_CHECKING:
    import datetime


@typing.final
@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PackageChange:
    package_name: str
    package_kind: typing.Literal["Formula", "Cask"]
    change_kind: typing.Literal["Added", "Updated", "Removed"]
    commit_hash: str
    commit_subject: str
    package_path: str


@typing.final
@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class TapDigest:
    tap_name: str
    package_changes: tuple[PackageChange, ...] = ()
    failure_message: str | None = None


def render_grouped_digest(
    digest_date: datetime.date,
    tap_digests: tuple[TapDigest, ...],
    *,
    max_changes: int | None = None,
) -> str:
    failed_count: typing.Final = sum(digest.failure_message is not None for digest in tap_digests)
    output_sections: typing.Final = [
        f"# Homebrew news — {digest_date.isoformat()}",
        (
            f"{len(tap_digests)} {'tap' if len(tap_digests) == 1 else 'taps'} tracked; {failed_count} failed. "
            "Period: 00:00 to 24:00 UTC, using first-parent commit timestamps."
        ),
    ]
    if failed_count:
        output_sections.append("**Partial digest:** some taps could not be collected. Their sections show the errors.")
    for tap_digest in tap_digests:
        output_sections.append(f"## [{tap_digest.tap_name}](https://github.com/{tap_digest.tap_name})")
        if tap_digest.failure_message is not None:
            output_sections.append(f"Collection failed: {escape_markdown(tap_digest.failure_message)}")
            continue
        displayed_changes = (
            tap_digest.package_changes[:max_changes] if max_changes is not None else tap_digest.package_changes
        )
        section_body = render_package_entries(tap_digest.tap_name, displayed_changes)
        output_sections.append(re.sub(r"^## ", "### ", section_body.rstrip(), flags=re.MULTILINE))
        if len(displayed_changes) < len(tap_digest.package_changes):
            output_sections.append(
                f"Showing {len(displayed_changes)} of {len(tap_digest.package_changes)} "
                "package file changes; this section is truncated."
            )
    return "\n\n".join(output_sections) + "\n"


def escape_markdown(raw_text: str) -> str:
    return re.sub(r"([\\`*_{}\[\]<>()!|#])", r"\\\1", raw_text.replace("\n", " ").replace("\r", " "))


def render_digest(tap_name: str, digest_date: datetime.date, package_changes: tuple[PackageChange, ...]) -> str:
    output_lines: typing.Final = [
        f"# Homebrew news — {digest_date.isoformat()}",
        "",
        f"Tap: [{tap_name}](https://github.com/{tap_name})",
        "",
        "Period: 00:00 to 24:00 UTC, using commit timestamps on the first-parent history.",
        "",
    ]
    return "\n".join(output_lines) + "\n" + render_package_entries(tap_name, package_changes)


def render_package_entries(tap_name: str, package_changes: tuple[PackageChange, ...]) -> str:
    output_lines: typing.Final[list[str]] = []
    if not package_changes:
        output_lines.append("No formula or cask changes in this period.")
        return "\n".join(output_lines) + "\n"

    output_lines.extend([f"{len(package_changes)} package file changes.", ""])
    for change_kind in ("Added", "Updated", "Removed"):
        grouped_changes = tuple(change for change in package_changes if change.change_kind == change_kind)
        if not grouped_changes:
            continue
        output_lines.extend([f"## {change_kind}", ""])
        for package_change in grouped_changes:
            commit_url = f"https://github.com/{tap_name}/commit/{package_change.commit_hash}"
            output_lines.append(
                f"- **{escape_markdown(package_change.package_name)}** ({package_change.package_kind}) — "
                f"{escape_markdown(package_change.commit_subject)} "
                f"([{package_change.commit_hash[:7]}]({commit_url}))"
            )
        output_lines.append("")
    return "\n".join(output_lines).rstrip() + "\n"
