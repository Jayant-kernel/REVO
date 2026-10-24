"""Process-only isolation writer probe; not a qualification producer."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.product_fixtures import make_golden
from verified_data_factory.products.errors import ProductConfigError
from verified_data_factory.products.isolation import register_roles


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--role", choices=("TRAIN", "EVAL"), required=True)
    args = parser.parse_args()
    try:
        register_roles(args.registry, [make_golden(1, "aggregation")], args.role)
    except (ProductConfigError, OSError):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
