"""knowledge.toml — every value that is about this project rather than about the tooling.

The namespaces, the terms the mechanical checks are about, the preset surveys, where the
code repository lives, how a route becomes a file glob, and where pages publish to. None of
it is hardcoded, so the same tooling serves a knowledge base about anything.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from knowledge.vocab import Checks, Vocabulary

PLACEHOLDER = re.compile(r"^\{\{[A-Z_]+\}\}$")
TARGETS = ("none", "directory", "github-wiki")


class ConfigError(RuntimeError):
    """knowledge.toml is missing a required key, or holds a value it cannot hold."""


@dataclass(frozen=True)
class Survey:
    name: str
    query: str


@dataclass(frozen=True)
class Dependencies:
    route_property: str = ""
    endpoint_property: str = ""
    route_glob: str = ""
    endpoint_glob: str = ""
    absorbed_prefixes: tuple[str, ...] = ()
    dynamic_segment: str = "{...}"
    dynamic_replacement: str = "*"

    @property
    def derives(self) -> bool:
        """Whether any glob can be derived from the graph at all. False leaves manual
        globs as the only dependency source — the shipped default, because a project that
        has not told this tool how its routes map to files should get no globs rather
        than a guessed pattern that silently matches the wrong thing, or nothing."""
        return bool(self.route_property and self.route_glob) or bool(
            self.endpoint_property and self.endpoint_glob
        )


@dataclass(frozen=True)
class Sidebar:
    title: str = ""
    order: tuple[str, ...] = ()
    reference: tuple[str, ...] = ()
    nested_under: dict[str, str] = field(default_factory=dict)
    header_before: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Publish:
    target: str = "none"
    remote: str = ""
    out_dir: str = ""
    committer_name: str = "github-actions[bot]"
    committer_email: str = "41898282+github-actions[bot]@users.noreply.github.com"
    sidebar: Sidebar = field(default_factory=Sidebar)


@dataclass(frozen=True)
class Config:
    project_name: str
    vocabulary: Vocabulary
    surveys: tuple[Survey, ...]
    code_repo: Path | None
    dependencies: Dependencies
    publish: Publish
    unconfigured: bool


def _clean(value) -> str:
    """An unsubstituted {{PLACEHOLDER}} reads as empty, so the shipped template loads."""
    text = str(value or "")
    return "" if PLACEHOLDER.match(text) else text


def _required(table: dict, section: str, key: str) -> str:
    value = _clean(table.get(key))
    if not value:
        raise ConfigError(f"knowledge.toml: {section}.{key} is required")
    return value


def _vocabulary(data: dict) -> Vocabulary:
    table = data.get("vocabulary", {})
    checks = Checks(
        rule_class=_clean(table.get("rule_class")),
        concept_class=_clean(table.get("concept_class")),
        concept_spec=_clean(table.get("concept_spec")),
        field_class=_clean(table.get("field_class")),
        field_name_pattern=_clean(table.get("field_name_pattern")),
        underscore_reserved=bool(table.get("underscore_reserved", False)),
        functional_properties=tuple(table.get("functional_properties", ())),
        verbatim_string_properties=tuple(table.get("verbatim_string_properties", ())),
    )
    return Vocabulary(
        ontology_file=_clean(table.get("ontology_file")) or "ontology.ttl",
        namespace=_required(table, "vocabulary", "namespace"),
        instances=_required(table, "vocabulary", "instances"),
        prefix=_required(table, "vocabulary", "prefix"),
        instance_prefix=_clean(table.get("instance_prefix")) or "app",
        checks=checks,
    )


def _publish(data: dict) -> Publish:
    table = data.get("publish", {})
    target = _clean(table.get("target")) or "none"
    if target not in TARGETS:
        raise ConfigError(
            f"knowledge.toml: publish.target is {target!r}; expected one of {', '.join(TARGETS)}"
        )
    bar = table.get("sidebar", {})
    return Publish(
        target=target,
        remote=_clean(table.get("remote")),
        out_dir=_clean(table.get("out_dir")),
        committer_name=_clean(table.get("committer_name")) or Publish.committer_name,
        committer_email=_clean(table.get("committer_email")) or Publish.committer_email,
        sidebar=Sidebar(
            title=_clean(bar.get("title")),
            order=tuple(bar.get("order", ())),
            reference=tuple(bar.get("reference", ())),
            nested_under=dict(bar.get("nested_under", {})),
            header_before=dict(bar.get("header_before", {})),
            labels=dict(bar.get("labels", {})),
        ),
    )


def _dependencies(data: dict) -> Dependencies:
    table = data.get("dependencies", {})
    dynamic_segment = _clean(table.get("dynamic_segment")) or "{...}"
    if "..." not in dynamic_segment:
        raise ConfigError(
            f"knowledge.toml: dependencies.dynamic_segment is {dynamic_segment!r};"
            " it must contain '...' to mark where the segment name goes (e.g. '{...}', '<...>')"
        )
    route_glob = _clean(table.get("route_glob"))
    if route_glob and "{segments}" not in route_glob:
        raise ConfigError(
            f"knowledge.toml: dependencies.route_glob is {route_glob!r};"
            " it must contain '{segments}' to mark where the route's path segments go"
        )
    endpoint_glob = _clean(table.get("endpoint_glob"))
    if endpoint_glob and "{path}" not in endpoint_glob:
        raise ConfigError(
            f"knowledge.toml: dependencies.endpoint_glob is {endpoint_glob!r};"
            " it must contain '{path}' to mark where the endpoint's path goes"
        )
    return Dependencies(
        route_property=_clean(table.get("route_property")),
        endpoint_property=_clean(table.get("endpoint_property")),
        route_glob=route_glob,
        endpoint_glob=endpoint_glob,
        absorbed_prefixes=tuple(table.get("absorbed_prefixes", ())),
        dynamic_segment=dynamic_segment,
        dynamic_replacement=_clean(table.get("dynamic_replacement")) or "*",
    )


def load_config(root: Path) -> Config:
    with (root / "knowledge.toml").open("rb") as handle:
        data = tomllib.load(handle)

    code_repo = _clean(data.get("repo", {}).get("code_repo"))

    return Config(
        project_name=_clean(data.get("project", {}).get("name")),
        vocabulary=_vocabulary(data),
        surveys=tuple(
            Survey(name=_clean(row.get("name")), query=_clean(row.get("query")))
            for row in data.get("ask", ())
        ),
        code_repo=(root / code_repo).resolve() if code_repo else None,
        dependencies=_dependencies(data),
        publish=_publish(data),
        unconfigured=bool(data.get("template", {}).get("unconfigured", False)),
    )
