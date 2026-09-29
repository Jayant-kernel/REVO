"""Config loading and content-identity tests (Phase 7, §41)."""

import pytest
import yaml

from verified_data_factory.products import (
    ProductConfig,
    SplitPolicy,
    config_from_dict,
    get_profile,
    load_product_config,
    product_config_id,
    split_policy_id,
)
from verified_data_factory.products.errors import ProductConfigError


def test_config_ids_deterministic_and_sensitive():
    config = ProductConfig(product_name="p", product_type="TRAIN")
    assert product_config_id(config) == product_config_id(config)
    changed = config.model_copy(update={"product_type": "BENCHMARK"})
    assert product_config_id(changed) != product_config_id(config)
    policy = SplitPolicy(seed=1)
    assert split_policy_id(policy) == split_policy_id(policy)
    assert split_policy_id(SplitPolicy(seed=2)) != split_policy_id(policy)


def test_load_product_config_yaml(tmp_path):
    path = tmp_path / "product.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "product": {
                    "product_name": "demo",
                    "product_type": "PUBLIC_EVAL",
                    "visibility": "PUBLIC",
                    "output_format": "jsonl",
                    "split_policy": {"seed": 11},
                }
            }
        ),
        encoding="utf-8",
    )
    config = load_product_config(path)
    assert config.product_name == "demo"
    assert config.split_policy.seed == 11


def test_load_product_config_malformed(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("product: [unclosed\n", encoding="utf-8")
    with pytest.raises(ProductConfigError):
        load_product_config(path)


def test_config_from_dict_rejects_unknown_product_type():
    with pytest.raises(ProductConfigError):
        config_from_dict({"product": {"product_name": "x", "product_type": "NOPE"}})


def test_unknown_profile_rejected():
    with pytest.raises(ProductConfigError):
        get_profile("NOPE")
