"""Helper functions to load the Quartznet model from original Nemo released checkpoint files.
"""

# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Copyright (c) 2021 scart97

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Tuple

import torch
from omegaconf import OmegaConf
from torch import nn
from torchaudio.datasets.utils import download_url, extract_archive

from thunder.quartznet.blocks import QuartznetBlock, init_weights

checkpoint_archives = {
    "QuartzNet15x5Base-En": "https://api.ngc.nvidia.com/v2/models/nvidia/nemospeechmodels/versions/1.0.0a5/files/QuartzNet15x5Base-En.nemo",
    "QuartzNet15x5Base-Zh": "https://api.ngc.nvidia.com/v2/models/nvidia/nemospeechmodels/versions/1.0.0a5/files/QuartzNet15x5Base-Zh.nemo",
    "QuartzNet5x5LS-En": "https://api.ngc.nvidia.com/v2/models/nvidia/nemospeechmodels/versions/1.0.0a5/files/QuartzNet5x5LS-En.nemo",
    "QuartzNet15x5NR-En": "https://api.ngc.nvidia.com/v2/models/nvidia/nemospeechmodels/versions/1.0.0a5/files/QuartzNet15x5NR-En.nemo",
}


def read_config(config_path: str) -> Tuple[nn.Module, nn.Module]:
    """Read .yaml config and creates the encoder and decoder modules

    Args:
        config_path: Hydra config describing the Quartznet model

    Returns:
        Encoder and decoder Modules randomly initializated
    """
    conf = OmegaConf.load(config_path)
    encoder_params = conf["encoder"]["params"]
    inplanes = encoder_params["feat_in"] * encoder_params.get("frame_splicing", 1)
    quartznet_conf = OmegaConf.to_container(encoder_params["jasper"])

    layers = []
    for cfg in quartznet_conf:
        cfg["planes"] = cfg.pop("filters")
        cfg["kernel_size"] = cfg.pop("kernel")

        layers.append(
            QuartznetBlock(
                inplanes=inplanes,
                **cfg,
            )
        )
        inplanes = cfg["planes"]
    encoder = nn.Sequential(*layers)

    encoder.apply(init_weights)

    decoder_params = conf["decoder"]["params"]
    decoder = torch.nn.Sequential(
        torch.nn.Conv1d(
            decoder_params["feat_in"],
            decoder_params["num_classes"] + 1,
            kernel_size=1,
            bias=True,
        )
    )
    decoder.apply(init_weights)

    return encoder, decoder


def load_quartznet_weights(
    config_path: str, weights_path: str
) -> Tuple[nn.Module, nn.Module]:
    """Load quartznet/Quartznet model from data present inside .nemo file

    Args:
        config_path : Path to the .yaml configuration file.
        weights_path : Path to the pytorch weights checkpoint


    Returns:
        Encoder and decoder Modules with the checkpoint weights loaded
    """
    encoder, decoder = read_config(config_path)

    weights = torch.load(weights_path)

    # We remove the 'encoder.' and 'decoder.' prefix from the weights to enable
    # compatibility to load with plain nn.Modules created by reading the config
    encoder_weights = {
        k.replace("encoder.", "").replace(".conv", "").replace(".res.0", ".res"): v
        for k, v in weights.items()
        if "encoder" in k
    }
    encoder.load_state_dict(encoder_weights, strict=True)

    decoder_weights = {
        k.replace("decoder.decoder_layers.", ""): v
        for k, v in weights.items()
        if "decoder" in k
    }
    decoder.load_state_dict(decoder_weights, strict=True)
    return encoder, decoder


def load_from_nemo(checkpoint_path: str) -> Tuple[nn.Module, nn.Module]:
    """Creates the model from the .nemo checkpoint file and load the weights.

    Args:
        checkpoint_path : Path to the .nemo checkpoint file

    Returns:
        Both encoder and decoder.
    """
    with TemporaryDirectory() as extract_path:
        extract_path = Path(extract_path)
        extract_archive(str(checkpoint_path), extract_path)
        encoder, decoder = load_quartznet_weights(
            extract_path / "model_config.yaml", extract_path / "model_weights.ckpt"
        )
    return encoder, decoder


def get_quartznet(
    name: str, checkpoint_folder: str = None
) -> Tuple[nn.Module, nn.Module]:
    """Get quartznet model by identifier.
        This method downloads the checkpoint, creates the corresponding model
        and load the weights.

    Args:
        name: Model identifier. Check checkpoint_archives.keys()
        checkpoint_folder: Folder where the checkpoint will be saved to.

    Returns:
        Encoder and decoder Modules with the checkpoint weights loaded
    """
    if checkpoint_folder is None:
        checkpoint_folder = Path.home() / ".thunder"
        checkpoint_folder.mkdir(exist_ok=True)

    url = checkpoint_archives[name]
    filename = url.split("/")[-1]
    checkpoint_path = Path(checkpoint_folder) / filename
    if not checkpoint_path.exists():
        download_url(
            url,
            download_folder=checkpoint_folder,
            resume=True,
        )
    filename = url.split("/")[-1]

    return load_from_nemo(checkpoint_path)
