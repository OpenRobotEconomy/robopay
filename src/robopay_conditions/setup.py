from setuptools import find_packages, setup

package_name = "robopay_conditions"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Your Name",
    maintainer_email="you@example.com",
    description="Condition node: bind physical-world predicates to robopay payments.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "condition_node = robopay_conditions.condition_node:main",
        ],
    },
)
