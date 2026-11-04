"""打印应用路由表：python scripts/routes.py [关键字]

不加关键字打印全部；加关键字只打印路径里包含该词的，例如：
    python scripts/routes.py order
    python scripts/routes.py auth
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402


def main() -> None:
    keyword = sys.argv[1] if len(sys.argv) > 1 else ""
    app = create_app("development")

    rules = [r for r in app.url_map.iter_rules() if keyword in r.rule]
    width = max((len(r.rule) for r in rules), default=0)

    print(f"{'方法':<8}{'路径':<{width}}  处理函数(endpoint)")
    print("-" * (8 + width + 20))
    for rule in sorted(rules, key=lambda r: r.rule):
        methods = ",".join(sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"}))
        print(f"{methods:<8}{rule.rule:<{width}}  {rule.endpoint}")


if __name__ == "__main__":
    main()