from setuptools import setup, find_packages

setup(
    name="agentchains-sdk",
    version="1.0.0",
    description="Python SDK for the AgentChains marketplace API",
    author="AgentChains",
    author_email="akhilreddydanda3@gmail.com",
    url="https://github.com/DandaAkhilReddy/agentchains",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=["httpx>=0.25"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
