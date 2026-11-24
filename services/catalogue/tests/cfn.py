"""Read template.yaml in tests.

CloudFormation short-form tags (!Ref, !Sub, !GetAtt, ...) aren't standard YAML, so a plain
yaml.safe_load rejects them. This loader keeps each tag as a one-key dict, e.g.
`!GetAtt EventsTable.Arn` -> {"!GetAtt": "EventsTable.Arn"}, so tests can inspect it.
"""

from functools import cache
from pathlib import Path
from typing import Any

import yaml

TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "template.yaml"


class _CfnLoader(yaml.SafeLoader):
    pass


def _construct_tag(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> dict[str, Any]:
    if isinstance(node, yaml.ScalarNode):
        value: Any = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {f"!{suffix}": value}


_CfnLoader.add_multi_constructor("!", _construct_tag)


@cache
def load_template() -> dict[str, Any]:
    # _CfnLoader extends SafeLoader, so this is still safe: no arbitrary Python objects.
    return yaml.load(TEMPLATE_PATH.read_text(encoding="utf-8"), Loader=_CfnLoader)


def resource(logical_id: str) -> dict[str, Any]:
    return load_template()["Resources"][logical_id]


def events_table_definition() -> dict[str, Any]:
    """The table's key/index design exactly as the template declares it."""
    props = resource("EventsTable")["Properties"]
    keys = ("BillingMode", "AttributeDefinitions", "KeySchema", "GlobalSecondaryIndexes")
    return {key: props[key] for key in keys}
