from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = [
        line.strip()
        for line in f.read().strip().splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="employee360",
    version="1.0.0",
    description="Production-grade Employee360 platform supporting 30,000 employees and 10.95M daily summaries",
    author="Employee360 Team",
    author_email="admin@employee360.local",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
    python_requires=">=3.10",
)
