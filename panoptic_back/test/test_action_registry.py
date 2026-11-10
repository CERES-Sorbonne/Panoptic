from enum import Enum

import pytest

from panoptic.core.plugin.action_registry import ActionRegistry
from panoptic.models.action_models import ActionContext


class Model(Enum):
    clip = "openai/clip"
    dino = "facebook/dino"
    siglip = "google/siglip"


def create(ctx, model: Model = Model.clip, high_resolution: bool = False, keep_ratio: bool = True):
    """Create a vector type.
    @model: the model
    @high_resolution: dino only
    @keep_ratio: siglip only
    """
    return dict(model=model, high_resolution=high_resolution, keep_ratio=keep_ratio)


@pytest.fixture
def registry():
    registry = ActionRegistry()
    registry.easy_add('ML', create, ['vector_type'], visible_if={
        'high_resolution': {'model': [Model.dino]},
        'keep_ratio': {'model': [Model.siglip.value]},
    })
    return registry


def test_conditions_are_sent_to_the_ui(registry):
    params = {p.name: p for p in registry.get_all()['ML.create'].params}
    assert params['model'].visible_if is None
    assert params['high_resolution'].visible_if[0].model_dump() == {'param': 'model', 'values': ['facebook/dino']}
    assert params['keep_ratio'].visible_if[0].model_dump() == {'param': 'model', 'values': ['google/siglip']}


@pytest.mark.parametrize("model,expected", [
    ('facebook/dino', (True, True)),     # keep_ratio hidden: its default
    ('google/siglip', (False, False)),   # high_resolution hidden: its default
    (None, (False, True)),               # model left to its default (clip): both hidden
])
def test_hidden_params_keep_their_default(registry, model, expected):
    inputs = {'high_resolution': True, 'keep_ratio': False}
    if model:
        inputs['model'] = model
    res = registry.call('ML.create', ActionContext(ui_inputs=inputs))
    assert (res['high_resolution'], res['keep_ratio']) == expected


def test_unknown_parameter_is_rejected():
    with pytest.raises(ValueError, match='typo'):
        ActionRegistry().easy_add('ML', create, visible_if={'typo': {'model': ['x']}})
