from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pyblazeb2",
    version="0.13",
    author="Mitchell Long",
    author_email='meechllada@gmail.com',
    description="A compact library for interacting with Backblaze b2 buckets",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mwlong23/pyblazeb2",
    packages=setuptools.find_packages(exclude=['contrib', 'docs', 'tests']),
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
    project_urls={
        'Source': 'https://github.com/mwlong23/pyblazeb2',
        'Tracker': 'https://github.com/mwlong23/pyblazeb2/issues',
    }
)
