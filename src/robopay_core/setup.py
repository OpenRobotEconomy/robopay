from setuptools import find_packages, setup

package_name = "robopay_core"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    package_data={"robopay_core": ["*.json"]},
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=[
        "setuptools",
        "web3>=7.0",
        "eth-account>=0.13",
        "cryptography>=42.0",
        "python-dotenv>=1.0",
    ],
    zip_safe=True,
    maintainer="Your Name",
    maintainer_email="you@example.com",
    description="Payment node, wallet providers, settlement backends, and CLI for robopay.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "payment_node = robopay_core.payment_node:main",
            "robopay = robopay_core.cli:main",
        ],
    },
)
