from setuptools import setup, find_packages
import os

setup(
	name="qbacmet",
	version="0.0.1",
	packages=find_packages(),
	install_requires=[
		## Add your package dependencies here
	],
	author="Srikar Chundury",
	author_email="srikar.chundury@gmail.com",
	description="A vendor-agnostic metrics/feature \"tap\" that can be attached to any quantum job sim/hardware without having to rewrite experiments.",
	long_description=open("README.md").read() if os.path.exists("README.md") else "",
	long_description_content_type="text/markdown",
	url="https://github.com/srikarchundury/qbacmet",
	python_requires=">=3.11",
)
