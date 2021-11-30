"""Functionality to register the multiple checkpoints and provide a unified loading interface.
"""

__all__ = ["register_checkpoint", "load_checkpoint_data"]

from functools import partial
from typing import Callable, Dict, Type

from thunder.citrinet.compatibility import CitrinetCheckpoint, load_citrinet_checkpoint
from thunder.quartznet.compatibility import (
    QuartznetCheckpoint,
    load_quartznet_checkpoint,
)
from thunder.utils import BaseCheckpoint, CheckpointResult
from thunder.wav2vec.compatibility import load_huggingface_checkpoint

CHECKPOINT_LOAD_FUNC_TYPE = Callable[..., CheckpointResult]

CHECKPOINT_REGISTRY: Dict[str, CHECKPOINT_LOAD_FUNC_TYPE] = {}


def register_checkpoint(
    checkpoints: Type[BaseCheckpoint], load_function: CHECKPOINT_LOAD_FUNC_TYPE
):
    """Register all variations of some checkpoint enum with the corresponding loading function

    Args:
        checkpoints : Base checkpoint class
        load_function : function to load the checkpoint,
            must receive one instance of `checkpoints` as first argument"""
    for checkpoint in checkpoints:
        CHECKPOINT_REGISTRY.update(
            {checkpoint.name: partial(load_function, checkpoint)}
        )


register_checkpoint(QuartznetCheckpoint, load_quartznet_checkpoint)
register_checkpoint(CitrinetCheckpoint, load_citrinet_checkpoint)


def load_checkpoint_data(checkpoint_name: str, **load_kwargs) -> CheckpointResult:
    """Load data from any registered checkpoint

    Args:
        checkpoint_name : Base checkpoint name, like "QuartzNet5x5LS_En" or "facebook/wav2vec2-large-960h"

    Returns:
        Object containing the checkpoint data (encoder, decoder, transforms and additional data).
    """
    # Special case when dealing with any huggingface model
    if "/" in checkpoint_name:
        model_data = load_huggingface_checkpoint(checkpoint_name, **load_kwargs)
    else:
        load_fn = CHECKPOINT_REGISTRY[checkpoint_name]
        model_data = load_fn(**load_kwargs)
    return model_data
